from sqlmodel import Session

from app import crud
from app.models import Item, ItemCreate
from app.tests.utils.utils import random_lower_string


def create_random_item(db: Session) -> Item:
    title = random_lower_string()
    description = random_lower_string()
    item_in = ItemCreate(title=title, description=description)
    # Directly create item without owner
    item = Item.model_validate(item_in)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item
