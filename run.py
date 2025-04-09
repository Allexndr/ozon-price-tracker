#!/usr/bin/env python3
"""
Simple script to run Ozon parser
"""
import asyncio
import os
import sys
from app.parser.ozon_parser import OzonParser
from app.parser.captcha_solver import TwoCaptchaSolver

async def main():
    """Main function to run the parser"""
    # Get API key from environment variable or use empty string
    captcha_api_key = os.environ.get('CAPTCHA_API_KEY', '')
    
    # Initialize CAPTCHA solver if API key is provided
    captcha_solver = None
    if captcha_api_key:
        captcha_solver = TwoCaptchaSolver(api_key=captcha_api_key)
        print("CAPTCHA solver initialized")
    else:
        print("No CAPTCHA API key provided. CAPTCHA solving will not be available.")
    
    # Initialize parser with CAPTCHA solver
    parser = OzonParser(captcha_solver=captcha_solver)
    
    # Start parsing
    print("Starting parser...")
    await parser.start_parse()

if __name__ == "__main__":
    # Run the parser
    asyncio.run(main())
