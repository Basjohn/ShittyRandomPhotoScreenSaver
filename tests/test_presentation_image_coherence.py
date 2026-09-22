from core.presentation_image_coherence import coherent_image_sources


def test_complete_generation_keeps_every_image():
    assert coherent_image_sources(("a", "b", "c")) == ("a", "b", "c")


def test_partial_generation_projects_no_images_until_complete():
    assert coherent_image_sources(("a", "", "c")) == ("", "", "")


def test_disabled_images_project_none_even_when_cache_is_complete():
    assert coherent_image_sources(("a", "b"), enabled=False) == ("", "")
