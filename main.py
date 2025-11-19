import os
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Product as ProductSchema

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Models ----------
class ProductCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: float = Field(..., ge=0)
    category: str
    in_stock: bool = True
    image_url: Optional[str] = None
    rating: Optional[float] = Field(4.5, ge=0, le=5)

class ProductOut(ProductCreate):
    id: str


# ---------- Helpers ----------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)


def product_doc_to_out(doc) -> ProductOut:
    return ProductOut(
        id=str(doc.get("_id")),
        title=doc.get("title"),
        description=doc.get("description"),
        price=float(doc.get("price", 0)),
        category=doc.get("category"),
        in_stock=bool(doc.get("in_stock", True)),
        image_url=doc.get("image_url"),
        rating=float(doc.get("rating", 0)) if doc.get("rating") is not None else None,
    )


# ---------- Base Routes ----------
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ---------- Product Routes ----------
@app.get("/api/products", response_model=List[ProductOut])
def list_products(limit: Optional[int] = None, category: Optional[str] = None):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    filters = {}
    if category:
        filters["category"] = category

    docs = get_documents("product", filters, limit)
    return [product_doc_to_out(doc) for doc in docs]


@app.get("/api/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        doc = db["product"].find_one({"_id": ObjectId(product_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid product id")

    if not doc:
        raise HTTPException(status_code=404, detail="Product not found")

    return product_doc_to_out(doc)


@app.post("/api/products", response_model=str)
def create_product(payload: ProductCreate):
    # Validate against schema (ensures fields are correct) - using pydantic via ProductCreate
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    product = payload.model_dump()
    inserted_id = create_document("product", product)
    return inserted_id


@app.post("/api/products/seed")
def seed_products():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    count = db["product"].count_documents({})
    if count > 0:
        return {"inserted": 0, "message": "Products already exist"}

    sample_products = [
        {
            "title": "Pastel Visa Card",
            "description": "Minimalist fintech card with soft-touch finish",
            "price": 29.99,
            "category": "Cards",
            "in_stock": True,
            "image_url": "https://images.unsplash.com/photo-1543002588-bfa74002ed7e?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.8,
        },
        {
            "title": "Digital Wallet Subscription",
            "description": "Secure multi-currency wallet with instant transfers",
            "price": 9.99,
            "category": "Services",
            "in_stock": True,
            "image_url": "https://images.unsplash.com/photo-1612178991541-baf93d77a9a0?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.7,
        },
        {
            "title": "Smart NFC Tag",
            "description": "Tap-to-pay accessory for seamless checkout",
            "price": 14.5,
            "category": "Accessories",
            "in_stock": True,
            "image_url": "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.4,
        },
        {
            "title": "Premium Card Holder",
            "description": "Matte silicone holder in pastel tones",
            "price": 19.0,
            "category": "Accessories",
            "in_stock": True,
            "image_url": "https://images.unsplash.com/photo-1537039557101-0e0f4e3d0f51?q=80&w=1200&auto=format&fit=crop",
            "rating": 4.6,
        },
    ]

    result = db["product"].insert_many(sample_products)
    return {"inserted": len(result.inserted_ids)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
