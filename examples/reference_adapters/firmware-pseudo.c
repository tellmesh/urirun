#include "../../adapters/c/urirun.h"
#include <string.h>
void led_set(int on);
void handle_uri(const char* uri) {
  urirun_descriptor_t d;
  if (urirun_parse(uri, &d) != 0) return;
  if (strcmp(d.package_name, "device") != 0) return;
  if (strcmp(d.target, "device-01") != 0) return;
  if (d.segment_count >= 3 && strcmp(d.segments[0], "led") == 0 && strcmp(d.segments[1], "set") == 0) {
    led_set(strcmp(d.segments[2], "on") == 0);
  }
}
