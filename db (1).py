from datetime import datetime, timedelta, timezone

from sqlalchemy import (BigInteger, DateTime, Integer, String, Text, create_engine,
                        func, select, update)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from config import DATABASE_URL, START_BONUS

url = DATABASE_URL
if url.startswith("postgres://"):
    url = url.replace("postgres://", "postgresql+psycopg2://", 1)
elif url.startswith("postgresql://"):
    url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(200), default="")
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Tx(Base):
    __tablename__ = "tx"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(String(300), default="")
    created: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tool: Mapped[str] = mapped_column(String(40))
    topic: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="running")
    created: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Topup(Base):
    __tablename__ = "topups"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


def init():
    Base.metadata.create_all(engine)
    if engine.dialect.name == "postgresql":  # eski Integer ustunlarni BIGINT ga o'tkazish
        from sqlalchemy import text
        for stmt in ("ALTER TABLE users ALTER COLUMN balance TYPE BIGINT",
                     "ALTER TABLE tx ALTER COLUMN amount TYPE BIGINT"):
            try:
                with engine.begin() as c:
                    c.execute(text(stmt))
            except Exception:  # noqa: BLE001
                pass


def get_or_create_user(uid: int, name: str, ref: int | None = None):
    with SessionLocal.begin() as s:
        u = s.get(User, uid)
        if u:
            return u, False
        if ref == uid or (ref and not s.get(User, ref)):
            ref = None
        u = User(id=uid, name=name[:200], balance=START_BONUS, referrer_id=ref)
        s.add(u)
        s.add(Tx(user_id=uid, amount=START_BONUS, kind="bonus", note="start bonus"))
        return u, True


def get_user(uid: int):
    with SessionLocal() as s:
        return s.get(User, uid)


def add_balance(uid: int, amount: int, kind: str, note: str = ""):
    with SessionLocal.begin() as s:
        s.execute(update(User).where(User.id == uid).values(balance=User.balance + amount))
        s.add(Tx(user_id=uid, amount=amount, kind=kind, note=note[:300]))


def charge(uid: int, price: int, note: str = "") -> bool:
    """Atomik yechish: balans yetmasa False."""
    with SessionLocal.begin() as s:
        r = s.execute(update(User).where(User.id == uid, User.balance >= price)
                      .values(balance=User.balance - price))
        if r.rowcount == 0:
            return False
        s.add(Tx(user_id=uid, amount=-price, kind="charge", note=note[:300]))
        return True


def create_job(uid: int, tool: str, topic: str, price: int) -> int:
    with SessionLocal.begin() as s:
        j = Job(user_id=uid, tool=tool, topic=topic[:2000], price=price)
        s.add(j)
        s.flush()
        return j.id


def finish_job(job_id: int, status: str):
    with SessionLocal.begin() as s:
        s.execute(update(Job).where(Job.id == job_id).values(status=status))


def list_jobs(uid: int, limit: int = 10):
    with SessionLocal() as s:
        return list(s.scalars(select(Job).where(Job.user_id == uid)
                              .order_by(Job.id.desc()).limit(limit)))


def count_today(uid: int, tool: str) -> int:
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    with SessionLocal() as s:
        return s.scalar(select(func.count(Job.id)).where(
            Job.user_id == uid, Job.tool == tool, Job.created >= since)) or 0


def log_chat(uid: int):
    with SessionLocal.begin() as s:
        s.add(Job(user_id=uid, tool="chat", price=0, status="done"))


def stats():
    with SessionLocal() as s:
        users = s.scalar(select(func.count(User.id))) or 0
        jobs = s.scalar(select(func.count(Job.id)).where(Job.tool != "chat")) or 0
        revenue = s.scalar(select(func.coalesce(func.sum(Job.price), 0)).where(Job.status == "done")) or 0
        return users, jobs, revenue


def create_topup(uid: int, amount: int) -> int:
    with SessionLocal.begin() as s:
        t = Topup(user_id=uid, amount=amount)
        s.add(t)
        s.flush()
        return t.id


def decide_topup(tid: int, status: str):
    """Faqat 'pending' holatdagini o'zgartiradi (ikki marta bosishdan himoya). Topup yoki None qaytaradi."""
    with SessionLocal.begin() as s:
        r = s.execute(update(Topup).where(Topup.id == tid, Topup.status == "pending").values(status=status))
        if r.rowcount == 0:
            return None
        return s.get(Topup, tid)


def list_topups(uid: int, limit: int = 5):
    with SessionLocal() as s:
        return list(s.scalars(select(Topup).where(Topup.user_id == uid).order_by(Topup.id.desc()).limit(limit)))


def set_balance(uid: int, amount: int):
    with SessionLocal.begin() as s:
        s.execute(update(User).where(User.id == uid).values(balance=amount))
        s.add(Tx(user_id=uid, amount=0, kind="set", note=f"balans {amount} ga o'rnatildi"))


def count_running(uid: int) -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count(Job.id)).where(Job.user_id == uid, Job.status == "running")) or 0


def recover_stuck():
    """Server qayta ishga tushganda 'running' qolgan ishlar o'lgan hisoblanadi: bekor qilinadi, pul qaytariladi."""
    out = []
    with SessionLocal.begin() as s:
        for j in s.scalars(select(Job).where(Job.status == "running", Job.tool != "chat")):
            j.status = "failed"
            s.execute(update(User).where(User.id == j.user_id).values(balance=User.balance + j.price))
            s.add(Tx(user_id=j.user_id, amount=j.price, kind="refund", note=f"job {j.id} (server qayta ishga tushdi)"))
            out.append((j.id, j.user_id, j.price))
    return out


def has_tx(uid: int, kind: str) -> bool:
    with SessionLocal() as s:
        return bool(s.scalar(select(func.count(Tx.id)).where(Tx.user_id == uid, Tx.kind == kind)))


def count_done(uid: int) -> int:
    with SessionLocal() as s:
        return s.scalar(select(func.count(Job.id)).where(Job.user_id == uid, Job.status == "done",
                                                         Job.tool != "chat")) or 0


def give_once(uid: int, amount: int, kind: str, note: str = "") -> bool:
    """Bir martalik bonus: oldin berilgan bo'lsa False."""
    with SessionLocal.begin() as s:
        if s.scalar(select(func.count(Tx.id)).where(Tx.user_id == uid, Tx.kind == kind)):
            return False
        s.execute(update(User).where(User.id == uid).values(balance=User.balance + amount))
        s.add(Tx(user_id=uid, amount=amount, kind=kind, note=note[:300]))
        return True
