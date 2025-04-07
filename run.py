import asyncio

from dotenv import load_dotenv

from app.bot import start_bot


load_dotenv()


async def main():
    await asyncio.gather(start_bot())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Stopped.")
