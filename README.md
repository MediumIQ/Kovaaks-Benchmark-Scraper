# Kovaaks-Benchmark-Scraper
A simple python tool that aims to extract, clean and format data from various kovaaks community benchmarks into a useable format for statistical analysis 

Currently, the script acts entirely as its own backend data engine. It simply navigates the kovaaks backend API to scrape necessary data (being respectful for rate limits). It outputs a structured JSON file at the end which I plan to utilise in a final front-end project that will contain many more features!

**You can view the `Example_Data.json` to see the example data I scraped (it's very brief just to provide an idea)**

**Depdencies?**

*Pandas* : Benchmarks are typically excel spreadsheets so this is a perfect library to read and handle that data typically raw data from openpyxl

*openpyxl* : To read excel spreadsheets

*requests* : Simply for making API requests and scraping relevant data

All depedencies will be stored in 'requirements.txt' and can simply be installed after cloning the repo via `pip install -r requirements.txt`

# Why make this?

I've always had a love for aim training and been part of many small niche communities looking for data like, % of players in each rank bracket, and various stats within each rank bracket etc. so I thought I'd make this for myself and friends/

# Future of this project?

This current python script is a keystone in my overall work, I want to branch this out into a full-stack web app that can provide myself and others with a centralised place to view various statistical data such as:

*Different benchmark stats* : **Avg fps , Avg ttk, Avg sens per sub category etc.**,

*Personalised data analysis* : **Through the stored kovaaks .CSV files, I want to make a responsive and well formatted UI that can provide huge personal insight for personal review for players on what they can improve on, maybe compared to higher ranking players etc.**

And in the end once that is done, I might branch out into making a software application that can provide even further data insight for players like tracking their mouse motion when inside of a aim-trainer, letting them track more in-depth data and see exact replays of their mouse motion for review etc.

# How to run?

*1. Clone the Repository*

*2. Ensure you have a valid benchmark excel spreadsheet in the `benchmarks/` folder.*

*3. Run `python build_config.py` to generate a useable benchmark config to be used by the main scraper*

*4. Run `Scraper.py` and wait for the `Example_Data.json` to be produced
