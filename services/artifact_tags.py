"""Backward-compatible imports – use services.layer_tags for new code."""
from services.layer_tags import (  # noqa: F401
    MAX_TAGS_PER_SUBJECT as MAX_TAGS_PER_ARTIFACT,
    apply_tag_filter,
    artifact_to_dict,
    enrich_artifact_dicts,
    list_layer_tags,
    parse_tag_slugs,
    set_artifact_tags,
    tag_filters_enabled,
    tags_enabled,
    tags_for_artifact,
    tags_by_artifact_ids,
    normalize_slug,
)
