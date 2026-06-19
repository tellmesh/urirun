#include "urihandler.h"
#include <string.h>

static int copy_token(char* dst, const char* start, size_t len) {
  if (len >= URIHANDLER_MAX_TEXT) return -1;
  size_t n = len;
  memcpy(dst, start, n);
  dst[n] = '\0';
  return 0;
}

static int is_path_end(char value) {
  return value == '\0' || value == '?' || value == '#';
}

int urihandler_parse(const char* uri, urihandler_descriptor_t* out) {
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
  if (target_end == p) return -1;
  if (copy_token(out->target, p, (size_t)(target_end - p)) != 0) return -1;

  if (*target_end != '/') {
    out->segment_count = 0;
    return 0;
  }

  out->segment_count = 0;
  p = target_end + 1;
  while (!is_path_end(*p)) {
    if (out->segment_count >= URIHANDLER_MAX_SEGMENTS) return -1;
    const char* next = p;
    while (!is_path_end(*next) && *next != '/') {
      next++;
    }
    if (next != p) {
      if (copy_token(out->segments[out->segment_count], p, (size_t)(next - p)) != 0) return -1;
    } else {
      out->segments[out->segment_count][0] = '\0';
    }
    out->segment_count++;
    if (is_path_end(*next)) break;
    p = next + 1;
  }
  return 0;
}
