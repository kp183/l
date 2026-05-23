import asyncio
import uuid
from app.database import AsyncSessionLocal
from app.models.org import Organization, OrgMember
from app.models.user import User
from app.models.project import Project
from app.models.api_key import APIKey
from app.services.api_keys import generate_api_key, get_key_prefix

async def main():
    async with AsyncSessionLocal() as session:
        # Create a test user
        user_id = uuid.uuid4()
        user = User(
            id=user_id,
            clerk_id="clerk_manual_test_user",
            email="manual_test@example.com",
            name="Manual Test User"
        )
        session.add(user)
        await session.flush()
        
        # Create a test org
        org_id = uuid.uuid4()
        org = Organization(
            id=org_id,
            name="Manual Test Org",
            slug="manual-test-org"
        )
        session.add(org)
        await session.flush()
        
        # Add user to org as owner
        member = OrgMember(
            org_id=org_id,
            user_id=user_id,
            role="owner"
        )
        session.add(member)
        await session.flush()
        
        # Create a test project
        project_id = uuid.uuid4()
        project = Project(
            id=project_id,
            org_id=org_id,
            name="Manual Test Project",
            slug="manual-test-project"
        )
        session.add(project)
        await session.flush()
        
        # Generate API key
        raw_key, key_hash = generate_api_key()
        api_key = APIKey(
            project_id=project_id,
            name="Manual Test Key",
            key_hash=key_hash,
            key_prefix=get_key_prefix(raw_key)
        )
        session.add(api_key)
        await session.commit()
        
        print("SUCCESSFULLY CREATED TEST RESOURCES!")
        print(f"Project ID: {project_id}")
        print(f"Raw API Key: {raw_key}")

if __name__ == "__main__":
    asyncio.run(main())
