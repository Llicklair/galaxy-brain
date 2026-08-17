#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────
# build-agent.sh -- Build the Galaxy Brain JVM crash-capture agent jar.
#
# Requirements: JDK 8+ (javac, jar) on PATH.
# Output:       gb-agent.jar in the current directory.
#
# Install:
#   export JAVA_TOOL_OPTIONS="-javaagent:/absolute/path/to/gb-agent.jar"
#
# That single env var injects the agent into every JVM process -- Java,
# Kotlin, Scala, Gradle, Maven, sbt, etc.
# ──────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Compiling GbAgent.java ..."
javac GbAgent.java

echo "==> Packaging gb-agent.jar ..."
jar cfm gb-agent.jar META-INF/MANIFEST.MF \
    GbAgent.class \
    GbAgent\$CrashRecord.class \
    GbAgent\$ExceptionInfo.class \
    GbAgent\$FrameInfo.class \
    GbAgent\$ProcessInfo.class \
    GbAgent\$GbCoroutineHandler.class \
    META-INF/services/kotlinx.coroutines.CoroutineExceptionHandler \
    2>/dev/null || true
# Some inner classes may not exist if Kotlin handler wasn't compiled;
# jar will warn but still produce a valid archive with what's available.

# Re-run with only the classes that actually exist to avoid a broken jar.
CLASSES=(GbAgent.class)
for cls in GbAgent\$*.class; do
    [ -f "$cls" ] && CLASSES+=("$cls")
done

jar cfm gb-agent.jar META-INF/MANIFEST.MF \
    "${CLASSES[@]}" \
    META-INF/services/kotlinx.coroutines.CoroutineExceptionHandler

echo "==> Built: $(pwd)/gb-agent.jar"
echo ""
echo "To activate globally:"
echo "  export JAVA_TOOL_OPTIONS=\"-javaagent:$(pwd)/gb-agent.jar\""
echo ""
echo "Or per-invocation:"
echo "  java -javaagent:$(pwd)/gb-agent.jar -jar your-app.jar"

# Clean up .class files (optional -- comment out to keep them).
# rm -f GbAgent*.class
