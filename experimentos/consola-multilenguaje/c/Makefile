# Galaxy Brain crash capture hook — C shared library
#
# Build:
#   make
#
# Install:
#   LD_PRELOAD=$(pwd)/gb-hook.so ./your_program
#
# Clean:
#   make clean

CC      ?= gcc
CFLAGS  ?= -Wall -Wextra -O2
TARGET   = gb-hook.so

.PHONY: all clean

all: $(TARGET)

$(TARGET): gb_hook.c
	$(CC) -shared -fPIC $(CFLAGS) -o $@ $< -rdynamic

clean:
	rm -f $(TARGET)
