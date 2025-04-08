#!/usr/bin/env python3
"""
Simple script to run Ozon parser
"""
import asyncio
from app.parser.ozon_parser import OzonParser

async def main():
    """Main function to run the parser"""
    parser = OzonParser()
    await parser.start_parse()

if __name__ == "__main__":
    # Run the parser
    asyncio.run(main())
