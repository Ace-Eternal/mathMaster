from app.db.session import SessionLocal
from app.models import KnowledgePoint, SolutionMethod


KNOWLEDGE_POINTS = [
    {"name": "立体几何", "level": 1, "sort_no": 10},
    {"name": "函数与导数", "level": 1, "sort_no": 20},
    {"name": "线面平行判定定理", "level": 2, "sort_no": 101},
    {"name": "线面平行性质定理", "level": 2, "sort_no": 102},
    {"name": "导数求单调区间", "level": 2, "sort_no": 201},
]

SOLUTION_METHODS = [
    {"name": "构造法"},
    {"name": "分类讨论"},
    {"name": "数形结合"},
    {"name": "中位线法"},
    {"name": "空间向量法"},
    {"name": "坐标法"},
    {"name": "换元法"},
    {"name": "待定系数法"},
]


def main() -> None:
    db = SessionLocal()
    try:
        for item in KNOWLEDGE_POINTS:
            exists = db.query(KnowledgePoint).filter(KnowledgePoint.name == item["name"]).first()
            if not exists:
                db.add(KnowledgePoint(subject="math", **item))
        for item in SOLUTION_METHODS:
            exists = db.query(SolutionMethod).filter(SolutionMethod.name == item["name"]).first()
            if not exists:
                db.add(SolutionMethod(subject="math", description=None, **item))
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    main()
