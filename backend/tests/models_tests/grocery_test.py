from backend.src.models.grocery import Grocery

def test_clean_name():
    new_grocery = Grocery()
    new_grocery.name = "test{} "
    new_grocery.clean_name()
    assert new_grocery.name == "test"