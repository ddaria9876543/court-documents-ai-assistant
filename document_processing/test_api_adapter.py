import json
import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).parent / "src")
)

from api_adapter import build_api_result


if len(sys.argv) < 2:
    print(
        "Использование: "
        "python test_api_adapter.py <путь_к_файлу>"
    )
    sys.exit(1)


file_path = Path(sys.argv[1])

result = build_api_result(file_path)

print(
    json.dumps(
        result,
        ensure_ascii=False,
        indent=2,
    )
)