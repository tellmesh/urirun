#include "urihandler_v2.h"
#include <stdio.h>
#include <string.h>

void led_set(const char* target, const char* const* args, size_t arg_count) {
  printf("device led set target=%s state=%s\n", target, arg_count ? args[0] : "");
}

void log_info_user_created(const char* target, const char* const* args, size_t arg_count) {
  printf("log sink=%s event=user-created arg0=%s\n", target, arg_count ? args[0] : "");
}

int main(void) {
  const uh2_route_t routes[] = {
    {"device", "led", "set", led_set},
    {"log", "info", "user-created", log_info_user_created},
  };
  const size_t route_count = sizeof(routes)/sizeof(routes[0]);

  uh2_dispatch("device://device-01/led/set/on", routes, route_count);
  uh2_dispatch("log://app/info/user-created", routes, route_count);

  return 0;
}
