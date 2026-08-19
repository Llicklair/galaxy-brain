--- gb-hook.lua ARREGLADO — se instala por LUA_INIT y replica el default a mano.
---
--- Dos defectos del original:
---   1. Era un WRAPPER (`lua gb-hook.lua script.lua`) pero gb-run.py lo cargaba
---      con LUA_INIT=@gb-hook.lua. Cargado asi no hay arg[1], asi que imprimia
---      "Usage:" y os.exit(1): el programa observado NO LLEGABA A EJECUTARSE.
---   2. Como wrapper, tras el fallo hacia error(err, 0) desde main(), de modo que
---      la traza que imprimia el interprete era la del HOOK, no la del programa.
---
--- Aqui el message handler de xpcall es el punto de OBSERVACION (corre antes de
--- desenrollar la pila, ve el stack real), y despues se replica a mano el informe
--- del interprete —"lua: <msg>\n<traceback>"— recortando los frames del hook.
--- Mismo texto, mismo exit code.
---
--- Install: LUA_INIT=@/ruta/gb-hook.lua

local NULO = setmetatable({}, {__tostring = function() return 'null' end})

-- ==================== JSON minimo ====================
local gb_trace_id, gb_parent_span = nil, nil
do
  local previo = os.getenv('TRACEPARENT') or ''
  local partes = {}
  for x in string.gmatch(previo, '[^-]+') do partes[#partes+1] = x end
  if #partes == 4 and #partes[2] == 32 then gb_trace_id = partes[2] end
  if #partes == 4 and #partes[3] == 16 then gb_parent_span = partes[3] end
end

local function json_escape(s)
    s = s:gsub('\\', '\\\\'):gsub('"', '\\"')
    s = s:gsub('\n', '\\n'):gsub('\r', '\\r'):gsub('\t', '\\t')
    s = s:gsub('[\x00-\x1f]', function(c) return string.format('\\u%04x', c:byte()) end)
    return s
end

local json_encode

local function json_value(v, depth)
    if v == nil or v == NULO then return 'null' end
    local t = type(v)
    if t == 'boolean' then return v and 'true' or 'false' end
    if t == 'number' then
        if v ~= v or v == math.huge or v == -math.huge then return '"' .. tostring(v) .. '"' end
        if math.type and math.type(v) == 'float' and v == math.floor(v) then
            return string.format('%d', v)
        end
        return tostring(v)
    end
    if t == 'string' then return '"' .. json_escape(v) .. '"' end
    if t == 'table' then return json_encode(v, (depth or 0) + 1) end
    return '"' .. json_escape(tostring(v)) .. '"'
end

json_encode = function(tbl, depth)
    depth = depth or 0
    if depth > 20 then return '"<max depth>"' end
    local n = #tbl
    local is_array = n > 0
    if is_array then
        for k in pairs(tbl) do
            if type(k) ~= 'number' or k < 1 or k > n or k ~= math.floor(k) then
                is_array = false; break
            end
        end
    elseif next(tbl) == nil then
        is_array = true  -- tabla vacia -> []
    end
    local parts = {}
    if is_array then
        for i = 1, n do parts[#parts + 1] = json_value(tbl[i], depth) end
        return '[' .. table.concat(parts, ',') .. ']'
    end
    for k, v in pairs(tbl) do
        parts[#parts + 1] = '"' .. json_escape(tostring(k)) .. '":' .. json_value(v, depth)
    end
    return '{' .. table.concat(parts, ',') .. '}'
end

-- ==================== helpers ====================
local SEP = package.config:sub(1, 1)

local function get_home()
    return os.getenv('HOME') or os.getenv('USERPROFILE') or '.'
end

local function file_exists(p)
    local f = io.open(p, 'r'); if f then f:close(); return true end; return false
end

local function get_cwd()
    local h = io.popen(SEP == '\\' and 'cd' or 'pwd')
    if not h then return '.' end
    local c = h:read('*l'); h:close()
    return c or '.'
end

local function project_root(cwd)
    local c = (cwd or ''):gsub('\\', '/')
    while c ~= '' do
        if file_exists(c .. '/.git') then return c end
        local parent = c:match('^(.+)/[^/]+$')
        if not parent then return NULO end
        c = parent
    end
    return NULO
end

local function mkdir_p(path)
    if SEP == '\\' then os.execute('mkdir "' .. path:gsub('/', '\\') .. '" 2>nul')
    else os.execute('mkdir -p "' .. path .. '" 2>/dev/null') end
end

-- ==================== captura ====================
local function frames_desde_pila(nivel)
    local frames = {}
    local i = nivel
    while true do
        local info = debug.getinfo(i, 'nSl')
        if not info then break end
        local src = info.source or '?'
        if src:sub(1, 1) == '@' then src = src:sub(2) end
        local locales = nil
        if i == nivel then
            locales = {}
            local j = 1
            while true do
                local nombre, valor = debug.getlocal(i, j)
                if not nombre then break end
                if nombre:sub(1, 1) ~= '(' then locales[nombre] = tostring(valor) end
                j = j + 1
            end
            if next(locales) == nil then locales = nil end
        end
        frames[#frames + 1] = {
            file = src,
            line = info.currentline or 0,
            column = 0,
            ['function'] = info.name or info.what or '?',
            locals = locales,
        }
        -- El main chunk del script observado cierra la pila util: por debajo solo
        -- quedan xpcall y los frames del propio hook, que no son del programa.
        if info.what == 'main' then break end
        i = i + 1
        if #frames >= 50 then break end
    end
    return frames
end

local function escribe(mensaje, traceback, frames)
    local cwd = get_cwd()
    local ppid = tonumber(os.getenv('GB_PPID'))
    local record = {
        schema = 2,
        ts = os.date('!%Y-%m-%dT%H:%M:%SZ'),
        session_id = os.getenv('GB_SESSION_ID') or 'unknown',
        -- W3C Trace Context: de quien venimos. Lua no tiene setenv portable,
        -- asi que puede ser HIJO en la cadena pero no padre — declarado.
        trace_id = gb_trace_id,
        parent_span = gb_parent_span,
        language = 'lua',
        exception = {
            type = 'LuaError',
            message = tostring(mensaje),
            origin = 'message_handler',
        },
        frames = frames,
        process = {
            cwd = cwd,
            project = project_root(cwd),
            argv_forma = NULO,
            runtime = _VERSION,
            pid = NULO,
            ppid = ppid or NULO,
        },
        traceback = traceback or NULO,
        capture_method = 'hook',
    }
    local dir = get_home() .. SEP .. '.galaxy-brain'
    mkdir_p(dir)
    local fh = io.open(dir .. SEP .. 'crashes.jsonl', 'a')
    if fh then fh:write(json_encode(record) .. '\n'); fh:close() end
end

--- Recorta del traceback los frames del propio hook: el interprete corta en
--- "in main chunk" del script del usuario y cierra con "[C]: in ?".
local function recorta(tb)
    local lineas = {}
    for l in (tb .. '\n'):gmatch('(.-)\n') do lineas[#lineas + 1] = l end
    -- El PRIMER "in main chunk" es el del script observado; los de despues son
    -- los del propio hook. Buscar desde el final se quedaba con los del hook.
    local corte = nil
    for i = 1, #lineas do
        if lineas[i]:match('in main chunk%s*$') then corte = i; break end
    end
    if not corte then return tb end
    local out = {}
    for i = 1, corte do out[#out + 1] = lineas[i] end
    out[#out + 1] = '\t[C]: in ?'
    return table.concat(out, '\n')
end

-- Replica msghandler() de lua.c: mismo texto, mismas reglas para objetos de error.
local function manejador(err)
    local msg
    local t = type(err)
    if t == 'string' then
        msg = err
    elseif t == 'number' then
        msg = tostring(err)
    else
        local mt = getmetatable(err)
        if mt and mt.__tostring then
            local ok, s = pcall(tostring, err)
            if ok and type(s) == 'string' then
                pcall(escribe, s, nil, frames_desde_pila(3))
                return s  -- lua.c devuelve el __tostring SIN traceback
            end
        end
        msg = string.format('(error object is a %s value)', t)
    end
    local tb = recorta(debug.traceback(msg, 2))
    pcall(escribe, msg, tb, frames_desde_pila(3))
    return tb
end

-- ==================== arranque via LUA_INIT ====================
local function arranca()
    if type(arg) ~= 'table' then return end
    -- createargtable() de lua.c indexa desde el script: si NO hay script (lua -e,
    -- lua -i, REPL) pone arg[0] = el propio interprete y no crea indices
    -- negativos. Sin arg[-1] no hay script que observar y hay que apartarse: si
    -- no, se intenta cargar lua.exe como fuente y se mata al programa.
    if arg[-1] == nil then return end
    -- El informe de lua.c se encabeza con progname: el EJECUTABLE tal cual se
    -- invoco (arg[-1]) — en Windows, la ruta entera de lua.exe. Escribir 'lua:'
    -- a pelo cambia la PRIMERA linea del stderr, que es la que lee un humano y
    -- la que casa cualquier parseo de logs. Medido: 162 bytes -> 111.
    _GB_PROG = tostring(arg[-1])
    local script = arg[0]
    if type(script) ~= 'string' or script == '' or script:sub(1, 1) == '-' then return end
    if not file_exists(script) then return end
    if script:match('gb%-hook%.lua$') then return end

    local chunk, err = loadfile(script)
    if not chunk then
        io.stderr:write(_GB_PROG .. ': ' .. tostring(err) .. '\n')
        os.exit(1, true)
    end
    local ok, res = xpcall(chunk, manejador, table.unpack(arg, 1, #arg))
    if not ok then
        io.stderr:write(_GB_PROG .. ': ' .. tostring(res) .. '\n')
        os.exit(1, true)
    end
    os.exit(0, true)
end

arranca()
