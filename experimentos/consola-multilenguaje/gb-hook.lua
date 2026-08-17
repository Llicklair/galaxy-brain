#!/usr/bin/env lua
--- Galaxy Brain crash capture launcher for Lua.
---
--- Wraps the user's script in xpcall, captures crash details (locals,
--- stack frames) via debug.getlocal/debug.getinfo, and writes a JSON
--- schema v2 record to ~/.galaxy-brain/crashes.jsonl before re-raising.
---
--- Usage:
---   lua gb-hook.lua user_script.lua [args...]

-- ===================================================================
-- Minimal JSON encoder (no external deps)
-- ===================================================================

local function json_escape(s)
    s = s:gsub('\\', '\\\\')
    s = s:gsub('"', '\\"')
    s = s:gsub('\n', '\\n')
    s = s:gsub('\r', '\\r')
    s = s:gsub('\t', '\\t')
    s = s:gsub('[\x00-\x1f]', function(c)
        return string.format('\\u%04x', c:byte())
    end)
    return s
end

local json_encode  -- forward declaration for recursion

local function json_encode_value(val, depth)
    depth = depth or 0
    if depth > 20 then return '"<max depth>"' end

    local t = type(val)
    if val == nil then
        return 'null'
    elseif t == 'boolean' then
        return val and 'true' or 'false'
    elseif t == 'number' then
        if val ~= val then return '"NaN"' end         -- NaN
        if val == math.huge then return '"Inf"' end
        if val == -math.huge then return '"-Inf"' end
        return tostring(val)
    elseif t == 'string' then
        return '"' .. json_escape(val) .. '"'
    elseif t == 'table' then
        return json_encode(val, depth + 1)
    else
        return '"' .. json_escape(tostring(val)) .. '"'
    end
end

json_encode = function(tbl, depth)
    depth = depth or 0
    if depth > 20 then return '"<max depth>"' end

    -- Detect array vs object: a table is an array if keys are 1..#tbl.
    local is_array = true
    local n = #tbl
    if n == 0 then
        -- could be empty array or empty object — treat as object if any key exists
        if next(tbl) ~= nil then is_array = false end
    else
        for k, _ in pairs(tbl) do
            if type(k) ~= 'number' or k < 1 or k > n or k ~= math.floor(k) then
                is_array = false
                break
            end
        end
    end

    local parts = {}
    if is_array then
        for i = 1, n do
            parts[#parts + 1] = json_encode_value(tbl[i], depth)
        end
        return '[' .. table.concat(parts, ',') .. ']'
    else
        for k, v in pairs(tbl) do
            local key = type(k) == 'string' and k or tostring(k)
            parts[#parts + 1] = '"' .. json_escape(key) .. '":' .. json_encode_value(v, depth)
        end
        return '{' .. table.concat(parts, ',') .. '}'
    end
end

-- ===================================================================
-- Helpers
-- ===================================================================

local function get_home()
    return os.getenv('HOME') or os.getenv('USERPROFILE') or '.'
end

local function path_join(...)
    local sep = package.config:sub(1, 1)  -- '/' or '\'
    return table.concat({...}, sep)
end

local function file_exists(path)
    local f = io.open(path, 'r')
    if f then f:close(); return true end
    return false
end

local function detect_project_root()
    -- Walk up from the working directory looking for .git
    local sep = package.config:sub(1, 1)
    -- Use io.popen to get cwd portably
    local handle = io.popen('cd')  -- Windows
    if not handle then
        handle = io.popen('pwd')   -- Unix
    end
    if not handle then return nil end
    local cwd = handle:read('*l')
    handle:close()
    if not cwd or cwd == '' then return nil end

    -- Normalise to forward slashes for easier manipulation.
    cwd = cwd:gsub('\\', '/')

    while true do
        local git_path = cwd .. '/.git'
        if file_exists(git_path) then
            return cwd
        end
        local parent = cwd:match('^(.+)/[^/]+$')
        if not parent then return nil end
        cwd = parent
    end
end

local function iso8601_now()
    return os.date('!%Y-%m-%dT%H:%M:%SZ')
end

local function mkdir_p(path)
    -- Best-effort recursive mkdir.
    local sep = package.config:sub(1, 1)
    if sep == '\\' then
        os.execute('mkdir "' .. path:gsub('/', '\\') .. '" 2>nul')
    else
        os.execute('mkdir -p "' .. path .. '" 2>/dev/null')
    end
end

-- ===================================================================
-- Crash capture
-- ===================================================================

local function capture_locals(level)
    local locals = {}
    local i = 1
    while true do
        local name, value = debug.getlocal(level, i)
        if not name then break end
        if name:sub(1, 1) ~= '(' then  -- skip internal vars like "(*temporary)")
            locals[name] = tostring(value)
        end
        i = i + 1
    end
    return locals
end

local function capture_stack(level)
    local frames = {}
    local i = level
    while true do
        local info = debug.getinfo(i, 'nSlf')
        if not info then break end
        frames[#frames + 1] = {
            source     = info.source or '?',
            short_src  = info.short_src or '?',
            what       = info.what or '?',
            name       = info.name,
            line       = info.currentline,
            linedefined = info.linedefined,
        }
        i = i + 1
        if #frames > 50 then break end  -- safety cap
    end
    return frames
end

local function write_crash(err_msg, locals, stack_frames)
    -- Build schema-v2 compliant frames from raw stack
    local v2_frames = {}
    for _, f in ipairs(stack_frames) do
        local src = f.source or '?'
        -- Strip leading '@' that Lua adds to file sources
        if src:sub(1, 1) == '@' then src = src:sub(2) end
        v2_frames[#v2_frames + 1] = {
            file     = src,
            line     = f.line or 0,
            column   = 0,
            ['function'] = f.name or f.what or '?',
            locals   = nil,  -- filled below for the crash frame
        }
    end
    -- Attach locals to the first user frame (the one that errored)
    if #v2_frames > 0 and locals and next(locals) then
        v2_frames[1].locals = locals
    end

    local cwd_handle = io.popen(package.config:sub(1,1) == '\\' and 'cd' or 'pwd')
    local cwd = cwd_handle and cwd_handle:read('*l') or '.'
    if cwd_handle then cwd_handle:close() end

    local session_id = os.getenv('GB_SESSION_ID') or 'unknown'
    -- Lua has no portable ppid; try GB_PPID env var set by gb-run.py
    local ppid_str = os.getenv('GB_PPID')
    local ppid_val = ppid_str and tonumber(ppid_str) or nil

    local record = {
        schema  = 2,
        ts      = iso8601_now(),
        session_id = session_id,
        language = 'lua',
        exception = {
            type    = 'runtime_error',
            message = tostring(err_msg),
            origin  = 'xpcall',
        },
        frames  = v2_frames,
        process = {
            cwd     = cwd,
            project = detect_project_root(),
            runtime = _VERSION,
            pid     = nil,
            ppid    = ppid_val,
        },
        traceback = debug.traceback(tostring(err_msg), 2),
        capture_method = 'hook',
    }

    local home = get_home()
    local dir  = path_join(home, '.galaxy-brain')
    local file = path_join(dir, 'crashes.jsonl')

    mkdir_p(dir)

    local fh = io.open(file, 'a')
    if fh then
        fh:write(json_encode(record) .. '\n')
        fh:close()
    else
        io.stderr:write('[gb-hook.lua] WARNING: could not write crash record to ' .. file .. '\n')
    end
end

-- ===================================================================
-- Error handler (runs before stack unwinds)
-- ===================================================================

local captured_locals = nil
local captured_stack  = nil

local function error_handler(err)
    -- Level 2 = the frame that errored (1 = this handler, 2 = caller).
    captured_locals = capture_locals(2)
    captured_stack  = capture_stack(2)
    write_crash(err, captured_locals, captured_stack)
    return err  -- return original error for re-raise
end

-- ===================================================================
-- Main: load and run the user script
-- ===================================================================

local function main()
    local script = arg[1]
    if not script then
        io.stderr:write('Usage: lua gb-hook.lua <script.lua> [args...]\n')
        os.exit(1)
    end

    -- Shift args so the user script sees its own args as arg[1], arg[2], ...
    local new_arg = { [0] = script }
    for i = 2, #arg do
        new_arg[i - 1] = arg[i]
    end
    arg = new_arg

    local chunk, load_err = loadfile(script)
    if not chunk then
        io.stderr:write('gb-hook.lua: failed to load script: ' .. tostring(load_err) .. '\n')
        os.exit(1)
    end

    local ok, err = xpcall(chunk, error_handler)
    if not ok then
        -- Re-raise so the original exit behaviour is preserved.
        error(err, 0)
    end
end

main()
