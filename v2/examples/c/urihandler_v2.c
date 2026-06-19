#include "urihandler_v2.h"
#include <string.h>

static int copy_token(char* dst, const char* start, size_t len) {
  if (len >= UH2_MAX_TEXT) return -1;
  size_t n = len;
  memcpy(dst, start, n);
  dst[n] = '\0';
  return 0;
}

static int is_path_end(char value) {
  return value == '\0' || value == '?' || value == '#';
}

int uh2_parse(const char* uri, uh2_descriptor_t* out) {
  if (!uri || !out) return -1;
  memset(out, 0, sizeof(*out));

  const char* scheme_end = strstr(uri, "://");
  if (!scheme_end) return -1;
  if (scheme_end == uri) return -1;
  if (copy_token(out->package_name, uri, (size_t)(scheme_end - uri)) != 0) return -1;

  const char* p = scheme_end + 3;
  const char* target_end = p;
  while (*target_end && *target_end != '/' && *target_end != '?' && *target_end != '#') {
    target_end++;
  }
  if (target_end == p || *target_end != '/') return -1;
  if (copy_token(out->target, p, (size_t)(target_end - p)) != 0) return -1;

  out->segment_count = 0;
  p = target_end + 1;
  while (!is_path_end(*p)) {
    if (out->segment_count >= UH2_MAX_SEGMENTS) return -1;
    const char* next = p;
    while (!is_path_end(*next) && *next != '/') {
      next++;
    }
    if (next != p) {
      if (copy_token(out->segments[out->segment_count], p, (size_t)(next - p)) != 0) return -1;
      out->segment_count++;
    }
    if (is_path_end(*next)) break;
    p = next + 1;
  }
  return out->segment_count >= 2 ? 0 : -2;
}
const uh2_route_t* uh2_resolve(const uh2_descriptor_t* d, const uh2_route_t* routes, size_t route_count) {
  for (size_t i = 0; i < route_count; ++i) {
    if (strcmp(routes[i].package_name, d->package_name) == 0 &&
        strcmp(routes[i].resource, d->segments[0]) == 0 &&
        strcmp(routes[i].operation, d->segments[1]) == 0) {
      return &routes[i];
    }
  }
  return 0;
}

int uh2_dispatch(const char* uri, const uh2_route_t* routes, size_t route_count) {
  uh2_descriptor_t d;
  if (uh2_parse(uri, &d) != 0) return -1;
  const uh2_route_t* route = uh2_resolve(&d, routes, route_count);
  if (!route || !route->handler) return -2;

  const char* args[UH2_MAX_SEGMENTS];
  size_t arg_count = 0;
  for (size_t i = 2; i < d.segment_count; ++i) {
    args[arg_count++] = d.segments[i];
  }
  route->handler(d.target, args, arg_count);
  return 0;
}
