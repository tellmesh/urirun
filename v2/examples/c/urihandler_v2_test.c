#include "urihandler_v2.h"
#include <assert.h>
#include <string.h>

static int led_called = 0;
static int log_called = 0;

static void led_set(const char* target, const char* const* args, size_t arg_count) {
  assert(strcmp(target, "device-01") == 0);
  assert(arg_count == 1);
  assert(strcmp(args[0], "on") == 0);
  led_called++;
}

static void log_info_user_created(const char* target, const char* const* args, size_t arg_count) {
  assert(strcmp(target, "app") == 0);
  assert(arg_count == 1);
  assert(strcmp(args[0], "42") == 0);
  log_called++;
}

int main(void) {
  uh2_descriptor_t d;
  assert(uh2_parse("device://device-01/led/set/on?trace=1#ui", &d) == 0);
  assert(strcmp(d.package_name, "device") == 0);
  assert(strcmp(d.target, "device-01") == 0);
  assert(d.segment_count == 3);
  assert(strcmp(d.segments[0], "led") == 0);
  assert(strcmp(d.segments[1], "set") == 0);
  assert(strcmp(d.segments[2], "on") == 0);
  assert(uh2_parse("not-a-uri", &d) != 0);
  assert(uh2_parse(NULL, &d) != 0);
  assert(uh2_parse("device://device-01/led", &d) != 0);

  const uh2_route_t routes[] = {
    {"device", "led", "set", led_set},
    {"log", "info", "user-created", log_info_user_created},
  };
  const size_t route_count = sizeof(routes) / sizeof(routes[0]);
  assert(uh2_dispatch("device://device-01/led/set/on", routes, route_count) == 0);
  assert(uh2_dispatch("log://app/info/user-created/42", routes, route_count) == 0);
  assert(uh2_dispatch("device://device-01/motor/set/on", routes, route_count) != 0);
  assert(led_called == 1);
  assert(log_called == 1);
  return 0;
}
