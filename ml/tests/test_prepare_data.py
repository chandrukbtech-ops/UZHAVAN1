from ml.prepare_data import condition_for_path, crop_for_path


def test_extracts_crop_and_condition_from_disease_folder():
    image_path = "dataset_clean_final/Corn__Common_Rust/photo.jpg"

    assert crop_for_path(image_path) == "corn"
    assert condition_for_path(image_path, "corn") == "common-rust"


def test_maps_maize_to_corn_and_eggplant_to_brinjal():
    assert crop_for_path("field/maize/healthy/leaf.jpg") == "corn"
    assert crop_for_path("field/eggplant/healthy/leaf.jpg") == "brinjal"


def test_uses_explicit_condition_for_crop_specific_flat_dataset():
    assert crop_for_path("IMG-20260123-WA0047.jpeg") is None
    assert condition_for_path("IMG-20260123-WA0047.jpeg", "mustard", "alternaria-leaf-spot") == "alternaria-leaf-spot"


def test_removes_repeated_crop_and_leaf_words_from_disease_label():
    image_path = "Brinjal/Diseased Brinjal Leaf - Cercospora Leaf Spot/27.jpg"

    assert condition_for_path(image_path, "brinjal") == "cercospora-leaf-spot"