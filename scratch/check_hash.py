from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
hash_val = "$2b$12$7J9yjik8FFzDZE/w7eGiseeq1ty31N99DEqsUI5IhHOONL48o4VIa"
print("Matches admin123?", pwd_context.verify("admin123", hash_val))
