#include "strata/core/types.hpp"

#include <cassert>

int main() {
  strata::core::Entity entity{{"ent_smoke"}, "building", "Smoke Test"};
  assert(entity.id.value == "ent_smoke");
  assert(entity.type == "building");
  return 0;
}

