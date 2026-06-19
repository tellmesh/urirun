#ifndef URIHANDLER_H
#define URIHANDLER_H
#include <stddef.h>
#define URIHANDLER_MAX_SEGMENTS 8
#define URIHANDLER_MAX_TEXT 64
typedef struct {
  char package_name[URIHANDLER_MAX_TEXT];
  char target[URIHANDLER_MAX_TEXT];
  char segments[URIHANDLER_MAX_SEGMENTS][URIHANDLER_MAX_TEXT];
  size_t segment_count;
} urihandler_descriptor_t;
int urihandler_parse(const char* uri, urihandler_descriptor_t* out);
#endif
