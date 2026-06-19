#ifndef URIHANDLER_V2_H
#define URIHANDLER_V2_H
#include <stddef.h>
#define UH2_MAX_SEGMENTS 8
#define UH2_MAX_TEXT 64
typedef struct {
  char package_name[UH2_MAX_TEXT];
  char target[UH2_MAX_TEXT];
  char segments[UH2_MAX_SEGMENTS][UH2_MAX_TEXT];
  size_t segment_count;
} uh2_descriptor_t;
typedef void (*uh2_handler_fn)(const char* target, const char* const* args, size_t arg_count);
typedef struct {
  const char* package_name;
  const char* resource;
  const char* operation;
  uh2_handler_fn handler;
} uh2_route_t;
int uh2_parse(const char* uri, uh2_descriptor_t* out);
const uh2_route_t* uh2_resolve(const uh2_descriptor_t* d, const uh2_route_t* routes, size_t route_count);
int uh2_dispatch(const char* uri, const uh2_route_t* routes, size_t route_count);
#endif
