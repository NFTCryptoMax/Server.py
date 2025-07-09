from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, date
from enum import Enum

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Enums for validation
class TenderStatus(str, Enum):
    OFFER = "Offer"
    ROUND_1 = "Round 1"
    ROUND_2 = "Round 2"
    ROUND_3 = "Round 3"
    ROUND_4 = "Round 4"
    BAFO = "BAFO"
    CONTRACT_SIGNED = "Contract Signed"
    WON = "Won"
    LOST = "Lost"

class PriorityLevel(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

# Define Models
class Tender(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    item: str
    customer: str
    tender_name: str
    status: TenderStatus
    start_date: date
    expiry_date: date
    due_date: datetime
    deal_value: float
    priority: PriorityLevel
    assigned_sales_rep: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class TenderCreate(BaseModel):
    item: str
    customer: str
    tender_name: str
    status: TenderStatus = TenderStatus.OFFER
    start_date: date
    expiry_date: date
    due_date: datetime
    deal_value: float
    priority: PriorityLevel
    assigned_sales_rep: str

class TenderUpdate(BaseModel):
    item: Optional[str] = None
    customer: Optional[str] = None
    tender_name: Optional[str] = None
    status: Optional[TenderStatus] = None
    start_date: Optional[date] = None
    expiry_date: Optional[date] = None
    due_date: Optional[datetime] = None
    deal_value: Optional[float] = None
    priority: Optional[PriorityLevel] = None
    assigned_sales_rep: Optional[str] = None

# Routes
@api_router.get("/")
async def root():
    return {"message": "Sales Dashboard API"}

@api_router.post("/tenders", response_model=Tender)
async def create_tender(tender_data: TenderCreate):
    tender_dict = tender_data.dict()
    tender_dict['start_date'] = tender_dict['start_date'].isoformat()
    tender_dict['expiry_date'] = tender_dict['expiry_date'].isoformat()
    tender_dict['due_date'] = tender_dict['due_date'].isoformat()
    
    tender_obj = Tender(**tender_dict)
    tender_dict = tender_obj.dict()
    tender_dict['start_date'] = tender_dict['start_date'].isoformat()
    tender_dict['expiry_date'] = tender_dict['expiry_date'].isoformat()
    tender_dict['due_date'] = tender_dict['due_date'].isoformat()
    
    await db.tenders.insert_one(tender_dict)
    return tender_obj

@api_router.get("/tenders", response_model=List[Tender])
async def get_tenders(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    customer: Optional[str] = None
):
    query = {}
    if status:
        query["status"] = status
    if priority:
        query["priority"] = priority
    if customer:
        query["customer"] = customer
    
    tenders = await db.tenders.find(query).to_list(1000)
    
    for tender in tenders:
        if isinstance(tender.get('start_date'), str):
            tender['start_date'] = datetime.fromisoformat(tender['start_date']).date()
        if isinstance(tender.get('expiry_date'), str):
            tender['expiry_date'] = datetime.fromisoformat(tender['expiry_date']).date()
        if isinstance(tender.get('due_date'), str):
            tender['due_date'] = datetime.fromisoformat(tender['due_date'])
    
    return [Tender(**tender) for tender in tenders]

@api_router.get("/tenders/{tender_id}", response_model=Tender)
async def get_tender(tender_id: str):
    tender = await db.tenders.find_one({"id": tender_id})
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    if isinstance(tender.get('start_date'), str):
        tender['start_date'] = datetime.fromisoformat(tender['start_date']).date()
    if isinstance(tender.get('expiry_date'), str):
        tender['expiry_date'] = datetime.fromisoformat(tender['expiry_date']).date()
    if isinstance(tender.get('due_date'), str):
        tender['due_date'] = datetime.fromisoformat(tender['due_date'])
    
    return Tender(**tender)

@api_router.put("/tenders/{tender_id}", response_model=Tender)
async def update_tender(tender_id: str, tender_update: TenderUpdate):
    update_data = {k: v for k, v in tender_update.dict().items() if v is not None}
    
    if 'start_date' in update_data:
        update_data['start_date'] = update_data['start_date'].isoformat()
    if 'expiry_date' in update_data:
        update_data['expiry_date'] = update_data['expiry_date'].isoformat()
    if 'due_date' in update_data:
        update_data['due_date'] = update_data['due_date'].isoformat()
    
    update_data['updated_at'] = datetime.utcnow()
    
    result = await db.tenders.update_one({"id": tender_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Tender not found")
    
    updated_tender = await db.tenders.find_one({"id": tender_id})
    
    if isinstance(updated_tender.get('start_date'), str):
        updated_tender['start_date'] = datetime.fromisoformat(updated_tender['start_date']).date()
    if isinstance(updated_tender.get('expiry_date'), str):
        updated_tender['expiry_date'] = datetime.fromisoformat(updated_tender['expiry_date']).date()
    if isinstance(updated_tender.get('due_date'), str):
        updated_tender['due_date'] = datetime.fromisoformat(updated_tender['due_date'])
    
    return Tender(**updated_tender)

@api_router.delete("/tenders/{tender_id}")
async def delete_tender(tender_id: str):
    result = await db.tenders.delete_one({"id": tender_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Tender not found")
    return {"message": "Tender deleted successfully"}

# Get unique filter values
@api_router.get("/tenders/filters/customers")
async def get_customers():
    customers = await db.tenders.distinct("customer")
    return {"customers": customers}

@api_router.get("/tenders/filters/sales-reps")
async def get_sales_reps():
    sales_reps = await db.tenders.distinct("assigned_sales_rep")
    return {"sales_reps": sales_reps}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()