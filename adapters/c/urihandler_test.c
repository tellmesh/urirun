#include "urihandler.h"
#include <assert.h>
#include <string.h>

int main(void) {
  urihandler_descriptor_t d;
  assert(urihandler_parse("device://device-01/led/set/on?trace=1#ui", &d) == 0);
  assert(strcmp(d.package_name, "device") == 0);
  assert(strcmp(d.target, "device-01") == 0);
  assert(d.segment_count == 3);
  assert(strcmp(d.segments[0], "led") == 0);
  assert(strcmp(d.segments[1], "set") == 0);
  assert(strcmp(d.segments[2], "on") == 0);
  assert(urihandler_parse("not-a-uri", &d) != 0);
  assert(urihandler_parse(NULL, &d) != 0);
  assert(urihandler_parse("device://target/a/b/c/d/e/f/g/h/i", &d) != 0);
  return 0;
}
