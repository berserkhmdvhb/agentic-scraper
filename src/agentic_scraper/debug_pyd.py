import inspect
from pydantic import model_validator

print("✅ model_validator source file:")
print(inspect.getsourcefile(model_validator))

print("\n✅ model_validator function definition:")
print(inspect.getsource(model_validator))
