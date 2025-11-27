"""
Quick database initialization script.
Run this to create all tables and seed initial data.
"""

if __name__ == "__main__":
    print("=" * 70)
    print("FastAPI Adventure in AI - Database Setup")
    print("=" * 70)
    
    # Step 1: Create tables
    print("\n[Step 1/2] Creating database tables...")
    try:
        from services.orm_service import engine
        from business.models import Base
        Base.metadata.create_all(bind=engine)
        print("✓ Database tables created successfully")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        exit(1)
    
    # Step 2: Seed data
    print("\n[Step 2/2] Seeding initial data...")
    try:
        from seed_data import (
            seed_game_ratings,
            seed_worlds,
            seed_ai_directive_settings,
            seed_account_levels,
            seed_admin_user
        )
        
        seed_game_ratings()
        seed_worlds()
        seed_ai_directive_settings()
        seed_account_levels()
        seed_admin_user()
        
        print("✓ Initial data seeded successfully")
    except Exception as e:
        print(f"✗ Error seeding data: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    
    print("\n" + "=" * 70)
    print("Database setup complete!")
    print("=" * 70)
    print("\nDefault login credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print("\n⚠️  IMPORTANT: Change the admin password after first login!")
    print("\nNext steps:")
    print("  1. Start AI server:  python ai_server.py")
    print("  2. Start API server: python main.py")
    print("  3. Start frontend:   cd ../adventure-client && npm start")
    print("=" * 70)
