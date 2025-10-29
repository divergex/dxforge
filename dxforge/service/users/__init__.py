from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from orchestrator.user import UserManager

router = APIRouter()
um = UserManager()

# Request schemas
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

# Register endpoint
@router.post("/register")
def register(req: RegisterRequest):
    try:
        user_id = um.create_user(req.username, req.password)
        return {"user_id": user_id, "msg": "User created successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Login endpoint
@router.post("/login")
def login(req: LoginRequest):
    token = um.authenticate(req.username, req.password)
    if token is None:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    return {"access_token": token, "token_type": "bearer"}
