# Development History


After project is initiated, it only contained `items` as resources. To add another resource `users` and establish relationship within `users` and `items`, the following steps were followed:

1. Model
Add a new User model in models/user.py

Add a foreign key in Item pointing to User

2. Schemas
Create UserCreate, UserRead, and optionally UserWithItems schemas

3. Router
Create users.py under api/v1/

Add endpoints for: POST /users, GET /users, GET /users/{id}

4. Service Layer
Add user_service.py with logic for user creation and retrieval

5. Dependency
Simulate get_current_user() to return a real user from the DB (instead of string)

6. Test
Create test_users.py to test user creation and relationships

