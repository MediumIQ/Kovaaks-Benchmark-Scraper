# This will soon be used for a more universal approach to benchmarks so we aren't hardcoding benchmark data for configs etc.

import pandas as pd
import json
import requests
import urllib.parse
import time
import os

# hardcoding the path to our main excel file
BENCHMARK_FILE = os.path.join("benchmarks", "S5 - Kovaaks - Improvement.xlsx")

def make_config():
    print("making config from excel and fetching ids...")
    
    # try to pull the energy scores from the instructions tab first
    try:
        instructions = pd.read_excel(BENCHMARK_FILE, sheet_name="Instructions", header=None)
        energy_map = {}
        
        # the ranks and scores are always stuck on rows 17 and 18
        for i in range(1, 13):
            rank_name = str(instructions.iloc[17, i]).strip()
            energy_val = int(instructions.iloc[18, i])
            energy_map[rank_name] = energy_val
    except Exception as e:
        print(f"error reading instructions: {e}")
        return
        
    # helper function to parse the actual scenario tabs
    def get_scenarios(sheet_name):
        try:
            df = pd.read_excel(BENCHMARK_FILE, sheet_name=sheet_name, header=None)
            
            # pull the target ranks from the very top row
            ranks = [
                str(df.iloc[0, 12]).strip(), str(df.iloc[0, 13]).strip(), 
                str(df.iloc[0, 14]).strip(), str(df.iloc[0, 15]).strip()
            ]
            
            scenarios = []
            current_category = ""
            current_subcategory = ""
            
            # skip headers, real data starts at row 2
            for index, row in df.iloc[2:].iterrows():
                cat = str(row[0]).strip()
                subcat = str(row[1]).strip()
                
                # excel merges cells for category names. we have to remember the last one we saw
                # so the empty rows still know what folder they belong in
                if cat != 'nan' and cat != '': current_category = cat
                if subcat != 'nan' and subcat != '': current_subcategory = subcat
                    
                scenario_name = str(row[2]).strip()
                if scenario_name == 'nan' or scenario_name == '':
                    continue
                    
                scores = [row[12], row[13], row[14], row[15]]
                
                try:
                    # hacky way to check if this row actually has real score numbers
                    # if float() fails, it drops to except and we just ignore the row
                    float(scores[0]) 
                    full_cat = f"{current_subcategory} {current_category}"
                    
                    scenarios.append({
                        "category": full_cat,
                        "scenario": scenario_name,
                        "thresholds": [{"rank": ranks[i], "score": float(scores[i])} for i in range(4)]
                    })
                except ValueError:
                    pass
                    
            return scenarios
        except Exception as e:
            print(f"couldnt read sheet {sheet_name}: {e}")
            return []

    # combine all three tabs together into one big list
    all_scenarios = (
        get_scenarios("Novice") + 
        get_scenarios("Intermediate") + 
        get_scenarios("Advanced")
    )

    # set up the empty skeleton for our json
    config = {
        "version": "Voltaic Season 5",
        "energy_map": energy_map,
        "categories": {}
    }
    
    # loop through everything and put it in the right category folder
    for s in all_scenarios:
        cat = s["category"]
        scen = s["scenario"]
        
        if cat not in config["categories"]:
            config["categories"][cat] = {}
            
        config["categories"][cat][scen] = {
            "id": None, # leaving this blank for now until we hit the api
            "thresholds": s["thresholds"]
        }

    # sort the scenarios alphabetically so the json looks clean
    ordered_categories = {}
    for cat in config["categories"].keys():
        ordered_categories[cat] = dict(sorted(config["categories"][cat].items()))
        
    config["categories"] = ordered_categories

    print("fetching leaderboard ids from kovaaks...")
    
    # add a user-agent so the server doesnt instantly block us, I'm honestly unsure if this is needed
    headers = {'User-Agent': 'Mozilla/5.0'} 
    
    for category_name, scenarios in config["categories"].items():
        for scenario_name, data in scenarios.items():
            print(f"looking up id for: {scenario_name}")
            
            # fix spaces in the name so the url doesnt break
            encoded_name = urllib.parse.quote(scenario_name)
            url = f"https://kovaaks.com/webapp-backend/scenario/popular?page=0&max=20&scenarioNameSearch={encoded_name}"
            
            try:
                res = requests.get(url, headers=headers, timeout=10)
                
                # 200 means it worked perfectly
                if res.status_code == 200:
                    api_data = res.json().get("data", [])
                    
                    for item in api_data:
                        if item.get("scenarioName") == scenario_name:
                            data["id"] = item.get("leaderboardId")
                            print(f"found id: {data['id']}")
                            break
                            
                # 429 means we are going too fast. server wants us to chill for a bit
                elif res.status_code == 429:
                    print("got rate limited, pausing for 30s")
                    time.sleep(30)
                    
            except Exception as e:
                print(f"error fetching id: {e}")
                
            # sleep for 1 second so we are polite and dont get banned
            time.sleep(1)

    # save the finished file
    print("saving to voltaic_config_final.json")
    with open("voltaic_config_final.json", "w") as f:
        json.dump(config, f, indent=4)
        
    print("all done!")

if __name__ == "__main__":
    make_config()