# Galaxy Brain crash capture hook for Elixir.
#
# Registers a :logger handler that captures crash reports and writes
# JSON schema v2 records to ~/.galaxy-brain/crashes.jsonl.
#
# ## Installation
#
# Add to your `config/config.exs` (or `config/runtime.exs`):
#
#     # Compile the module first — add gb_hook.exs to your project or
#     # define the module in lib/gb_hook.ex with the code below.
#
#     config :logger,
#       handle_otp_reports: true
#
# Then in your `application.ex` start/2 callback (or a :logger config block):
#
#     GbHook.install()
#
# That's it. Crash reports from any process will be captured.

defmodule GbHook do
  @moduledoc """
  Galaxy Brain crash capture via Erlang's :logger.

  Registers a handler that intercepts crash reports and persists them
  as JSON schema v2 records to `~/.galaxy-brain/crashes.jsonl`.
  """

  @handler_id :gb_hook_crash_handler

  @doc """
  Installs the Galaxy Brain :logger handler. Idempotent — calling it
  multiple times is safe (subsequent calls are no-ops).
  """
  def install do
    case :logger.add_handler(@handler_id, __MODULE__, %{level: :error}) do
      :ok -> :ok
      {:error, {:already_exist, _}} -> :ok
      {:error, reason} -> {:error, reason}
    end
  end

  @doc """
  Removes the Galaxy Brain :logger handler.
  """
  def uninstall do
    :logger.remove_handler(@handler_id)
  end

  # -----------------------------------------------------------------------
  # :logger handler callbacks
  # -----------------------------------------------------------------------

  @doc false
  def adding_handler(config) do
    {:ok, config}
  end

  @doc false
  def removing_handler(_config) do
    :ok
  end

  @doc false
  def changing_config(_action, _old, new) do
    {:ok, new}
  end

  @doc false
  def log(%{level: level, msg: msg, meta: meta}, _config) when level in [:error, :critical, :alert, :emergency] do
    if crash_report?(msg) do
      try do
        record = build_crash_record(msg, meta)
        write_crash(record)
      rescue
        _ -> :ok  # never let the hook itself crash
      catch
        _, _ -> :ok
      end
    end
    :ok
  end

  def log(_event, _config), do: :ok

  # -----------------------------------------------------------------------
  # Crash detection and record building
  # -----------------------------------------------------------------------

  defp crash_report?({:report, %{label: {_, :crash}}}) do
    true
  end

  defp crash_report?({:report, report}) when is_map(report) do
    report
    |> Map.values()
    |> Enum.any?(fn
      val when is_binary(val) -> String.contains?(val, "crash")
      _ -> false
    end)
  end

  defp crash_report?({:string, msg}) when is_list(msg) do
    to_string(msg) |> String.contains?("crash")
  end

  defp crash_report?({:string, msg}) when is_binary(msg) do
    String.contains?(msg, "crash")
  end

  defp crash_report?({:report, report}) when is_list(report) do
    # OTP crash reports come as keyword lists
    Keyword.has_key?(report, :crashlog) or
      Keyword.has_key?(report, :crash_reason) or
      report_contains_crash?(report)
  end

  defp crash_report?(_), do: false

  defp report_contains_crash?(report) when is_list(report) do
    Enum.any?(report, fn
      {_k, v} when is_binary(v) -> String.contains?(v, "crash")
      {_k, v} when is_list(v) -> report_contains_crash?(v)
      _ -> false
    end)
  end

  defp report_contains_crash?(_), do: false

  defp build_crash_record(msg, meta) do
    {error_info, stack_info} = extract_crash_details(msg, meta)

    %{
      schema: 2,
      ts: DateTime.utc_now() |> DateTime.to_iso8601(),
      lang: "elixir",
      origin: "process",
      project: detect_project_root(),
      error: error_info,
      process: extract_process_info(meta),
      stack: stack_info
    }
  end

  defp extract_crash_details({:report, %{report: report_data}}, _meta) do
    extract_from_report_data(report_data)
  end

  defp extract_crash_details({:report, report}, _meta) when is_list(report) do
    extract_from_report_data(report)
  end

  defp extract_crash_details({:report, report}, _meta) when is_map(report) do
    reason = Map.get(report, :reason, "unknown")
    {
      %{type: "crash_report", message: safe_inspect(reason)},
      []
    }
  end

  defp extract_crash_details({:string, msg}, _meta) do
    {
      %{type: "crash_report", message: safe_to_string(msg)},
      []
    }
  end

  defp extract_crash_details(_msg, _meta) do
    {
      %{type: "crash_report", message: "unknown crash"},
      []
    }
  end

  defp extract_from_report_data(report) when is_list(report) do
    # OTP crash reports typically have two parts:
    # [{:initial_call, ...}, {:pid, ...}, {:registered_name, ...},
    #  {:error_info, {type, reason, stacktrace}}, ...]
    error_info = Keyword.get(report, :error_info)
    last_message = Keyword.get(report, :message)
    state = Keyword.get(report, :state)

    {error_map, stack} = case error_info do
      {type, reason, stacktrace} ->
        {
          %{
            type: safe_inspect(type),
            reason: safe_inspect(reason),
            message: safe_inspect(reason),
            last_message: safe_inspect(last_message),
            state: safe_inspect(state)
          },
          format_stacktrace(stacktrace)
        }
      _ ->
        {
          %{
            type: "crash_report",
            message: safe_inspect(report),
            last_message: safe_inspect(last_message),
            state: safe_inspect(state)
          },
          []
        }
    end

    {error_map, stack}
  end

  defp extract_from_report_data(report) do
    {%{type: "crash_report", message: safe_inspect(report)}, []}
  end

  defp extract_process_info(meta) do
    %{
      pid: safe_inspect(Map.get(meta, :pid)),
      registered_name: safe_inspect(Map.get(meta, :registered_name)),
      gl: safe_inspect(Map.get(meta, :gl)),
      mfa: case Map.get(meta, :mfa) do
        {m, f, a} -> "#{m}.#{f}/#{a}"
        other -> safe_inspect(other)
      end
    }
  end

  defp format_stacktrace(stacktrace) when is_list(stacktrace) do
    Enum.map(stacktrace, fn
      {mod, fun, arity, location} ->
        %{
          module: safe_inspect(mod),
          function: "#{fun}",
          arity: if(is_integer(arity), do: arity, else: safe_inspect(arity)),
          file: Keyword.get(location, :file) |> safe_to_string(),
          line: Keyword.get(location, :line)
        }
      {mod, fun, arity} ->
        %{
          module: safe_inspect(mod),
          function: "#{fun}",
          arity: if(is_integer(arity), do: arity, else: safe_inspect(arity))
        }
      other ->
        %{raw: safe_inspect(other)}
    end)
  end

  defp format_stacktrace(_), do: []

  # -----------------------------------------------------------------------
  # Helpers
  # -----------------------------------------------------------------------

  defp detect_project_root do
    case File.cwd() do
      {:ok, cwd} -> walk_up_for_git(cwd)
      _ -> nil
    end
  end

  defp walk_up_for_git(dir) do
    if File.dir?(Path.join(dir, ".git")) do
      dir
    else
      parent = Path.dirname(dir)
      if parent == dir do
        nil  # reached filesystem root
      else
        walk_up_for_git(parent)
      end
    end
  end

  defp write_crash(record) do
    home = System.get_env("HOME") || System.get_env("USERPROFILE") || "."
    dir = Path.join(home, ".galaxy-brain")
    file = Path.join(dir, "crashes.jsonl")

    File.mkdir_p!(dir)
    json = json_encode(record)
    File.write!(file, json <> "\n", [:append])
  end

  # -----------------------------------------------------------------------
  # Minimal JSON encoder (no Jason/Poison dependency)
  # -----------------------------------------------------------------------

  defp json_encode(value) when is_map(value) do
    pairs = Enum.map(value, fn {k, v} ->
      json_encode_string(to_string(k)) <> ":" <> json_encode(v)
    end)
    "{" <> Enum.join(pairs, ",") <> "}"
  end

  defp json_encode(value) when is_list(value) do
    items = Enum.map(value, &json_encode/1)
    "[" <> Enum.join(items, ",") <> "]"
  end

  defp json_encode(value) when is_binary(value), do: json_encode_string(value)
  defp json_encode(value) when is_integer(value), do: Integer.to_string(value)
  defp json_encode(value) when is_float(value), do: Float.to_string(value)
  defp json_encode(true), do: "true"
  defp json_encode(false), do: "false"
  defp json_encode(nil), do: "null"
  defp json_encode(value) when is_atom(value), do: json_encode_string(Atom.to_string(value))
  defp json_encode(value), do: json_encode_string(inspect(value))

  defp json_encode_string(s) do
    escaped = s
    |> String.replace("\\", "\\\\")
    |> String.replace("\"", "\\\"")
    |> String.replace("\n", "\\n")
    |> String.replace("\r", "\\r")
    |> String.replace("\t", "\\t")
    "\"" <> escaped <> "\""
  end

  defp safe_inspect(nil), do: nil
  defp safe_inspect(val) do
    try do
      inspect(val, limit: 200, printable_limit: 500)
    rescue
      _ -> "<uninspectable>"
    end
  end

  defp safe_to_string(val) when is_binary(val), do: val
  defp safe_to_string(val) when is_list(val) do
    try do
      to_string(val)
    rescue
      _ -> inspect(val)
    end
  end
  defp safe_to_string(nil), do: nil
  defp safe_to_string(val), do: inspect(val)
end
