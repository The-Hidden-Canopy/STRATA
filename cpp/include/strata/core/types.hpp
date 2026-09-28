#pragma once

#include <optional>
#include <string>

namespace strata::core {

template <typename Tag>
struct TypedId {
  std::string value;
  friend bool operator==(const TypedId&, const TypedId&) = default;
};

struct EntityTag {};
struct StateTag {};
struct SourceTag {};
struct GeometryTag {};

using EntityId = TypedId<EntityTag>;
using StateId = TypedId<StateTag>;
using SourceId = TypedId<SourceTag>;
using GeometryId = TypedId<GeometryTag>;

struct HistoricalDate {
  std::string raw;
  std::optional<std::string> earliest;
  std::optional<std::string> latest;
  std::string precision;
  std::string relation = "exact";
};

struct Uncertainty {
  float source_reliability = 0.0F;
  float temporal_precision = 0.0F;
  float spatial_precision = 0.0F;
  float semantic_confidence = 0.0F;
  float entity_match_confidence = 0.0F;
  float reconstruction_confidence = 0.0F;
};

struct Entity {
  EntityId id;
  std::string type;
  std::string canonical_name;
};

}  // namespace strata::core

