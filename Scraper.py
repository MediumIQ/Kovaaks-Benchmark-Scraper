import requests
import time
import math
import random
import json
from collections import defaultdict, Counter

# global vars
CONFIG_FILE = "voltaic_config_final.json" # I want to drastically change how configs work to support more benchmarks and be universal
PAGE_SIZE = 100 # max kovaaks backend lets us take at once

# figure out the energy score based on the rank thresholds.
# right now this only works for energy benchmarks, need to fix this later to be more flexible.
def calculate_dynamic_energy(score, thresholds, energy_map):
    # if they scored below the lowest rank, calculate a partial score
    if score <= thresholds[0]["score"]:
        gap_score = thresholds[1]["score"] - thresholds[0]["score"]
        energy_tier_1 = energy_map[thresholds[1]["rank"]]
        energy_tier_0 = energy_map[thresholds[0]["rank"]]
        gap_energy = energy_tier_1 - energy_tier_0
        
        virtual_floor_score = thresholds[0]["score"] - gap_score
        virtual_floor_energy = energy_tier_0 - gap_energy
        
        if gap_score == 0: return 0 
        progress = (score - virtual_floor_score) / gap_score
        raw_energy = virtual_floor_energy + (progress * gap_energy)
        return max(0, math.trunc(raw_energy))

    # cap the score if they beat the highest rank
    if score >= thresholds[-1]["score"]:
        return energy_map[thresholds[-1]["rank"]]

    # figure out which two ranks the score is between
    for i in range(len(thresholds) - 1):
        base = thresholds[i]
        next_tier = thresholds[i+1]

        if base["score"] <= score <= next_tier["score"]:
            gap_score = next_tier["score"] - base["score"]
            base_energy = energy_map[base["rank"]]
            next_tier_energy = energy_map[next_tier["rank"]]
            
            if gap_score == 0: return base_energy
            progress = (score - base["score"]) / gap_score
            gap_energy = next_tier_energy - base_energy
            raw_energy = base_energy + (progress * gap_energy)
            return math.trunc(raw_energy)
            
    return 0

# goes through a category and finds their highest energy run
def calculate_subcategory_energy(player_scores, subcategory_data, energy_map):
    best_energy = 0
    for scenario_name, scenario_rules in subcategory_data.items():
        if scenario_name in player_scores:
            score = player_scores[scenario_name]
            energy = calculate_dynamic_energy(score, scenario_rules["thresholds"], energy_map)
            if energy > best_energy:
                best_energy = energy
    return best_energy

# matches the average energy to the actual rank name
def get_overall_rank(average_energy, energy_map):
    sorted_ranks = sorted(energy_map.items(), key=lambda item: item[1], reverse=True)
    for rank_name, required_energy in sorted_ranks:
        if average_energy >= required_energy:
            return rank_name
    return "Unranked"

# main scraping function
def Run_Scraper():
    print("Attempting to open config file...!")

    # load the config we made
    try:
        with open(CONFIG_FILE,"r") as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Couldn't load file: '{CONFIG_FILE}'")
        return
    
    # dictionary to store all the player data we scrape
    unified_players = defaultdict(lambda: {
        "country": "N/A",
        "is_subscribed": False,
        "scenarios": {},
        "player_metrics": defaultdict(list) 
    })
    
    for Categoryname, CategoryData in config["categories"].items():
        for Scenario_name, Scenario_data in CategoryData.items():
            Current_scen_id = Scenario_data.get("id")

            # skip if we don't have an id for it yet
            if not Current_scen_id: continue

            print(f"Currently working on scenario: {Scenario_name} Inside of category: {Categoryname}")
            print(f"Scenario Name: {Scenario_name}, Scenario Data: {Scenario_data}", end="\n")

            page = 0
            max_retries = 3
            retry_count = 0
            success = False

            while True:
                print(f"Fetching page: {page}", end="\n")
                url = f"https://kovaaks.com/webapp-backend/leaderboard/scores/global?leaderboardId={Current_scen_id}&page={page}&max={PAGE_SIZE}"

                # keep trying if the server times out
                while retry_count < max_retries:
                    try:
                        response = requests.get(url, timeout=10)
                        
                        # kovaaks rate limit is annoying, gotta wait 2 mins if we hit it
                        if response.status_code == 429: 
                            time.sleep(120)
                            continue

                        response.raise_for_status()
                        players = response.json().get("data")

                        success = True
                        break
                    except requests.exceptions.RequestException as e:
                        retry_count += 1
                        print(f"Error in fetching the data on page: {page}, attempting to retry")
                        time.sleep(2 ** retry_count)

                if not success:
                    print("")
                    break

                if len(players) == 0:
                    print(f"Scenario: {Scenario_name} has finished scraping!, Total page count: {page}")
                    break

                # stopping at 10 pages for now so it doesn't take forever
                if page >= 10:
                    print("Stopping early...")
                    break

                for p in players:
                    steam_id = p.get("steamId")
                    attributes = p.get("attributes", {}) 

                    player_score =  p.get("score", 0)
                    player_country = p.get("country").upper() if p.get("country") else "N/A"
                    player_subscription_status =  p.get("kovaaksPlusActive", False)

                    # pull out their hardware and game settings
                    player_field_of_view = attributes.get("fov",0)
                    player_sensitivity = attributes.get("cm360", 0)
                    player_average_fps = attributes.get("avgFps", 0)
                    player_average_ttk = attributes.get("avgTtk", 0)
                    player_resolution = attributes.get("resolution", 0)

                    # only save realistic settings so fake data doesn't mess up the averages
                    if 5 < player_sensitivity < 200 and player_average_fps > 10:
                        unified_players[steam_id]["player_metrics"][Categoryname].append({
                            "hardware" : {
                                "fps" : player_average_fps,
                                "resolution" : player_resolution
                            },
                            "settings" : {
                                "cm360" : player_sensitivity,
                                "fov" : player_field_of_view
                            },
                            "performance" : {
                                "ttk" : player_average_ttk
                            }
                        })
                    unified_players[steam_id]["country"] = player_country
                    unified_players[steam_id]["is_subscribed"] = player_subscription_status
                    unified_players[steam_id]["scenarios"][Scenario_name] = player_score

                page += 1
                time.sleep(random.uniform(1.5,3.5))

    # filter out players who didn't play everything
    valid_players = []
    energy_map = config.get("energy_map", {})
    num_categories = len(config.get("categories", {}))

    for Steam_ID, player_data in unified_players.items():
        player_energy = 0
        player_valid = True

        for category_name, category_scenarios in config.get("categories", {}).items():
            highest_category_energy = calculate_subcategory_energy(player_data["scenarios"], category_scenarios, config.get("energy_map", {}))

            # kick them out if they missed a category completely
            if highest_category_energy == 0:
                player_valid = False
                break

            player_energy += highest_category_energy

        if player_valid:
            category_averages = {}
            
            for category_name, player_metrics in player_data["player_metrics"].items():
                if len(player_metrics) > 0:
                    # set up the empty dictionary for their averages
                    category_averages[category_name] = {"hardware": {}, "settings": {}, "performance": {}}
                    blueprint = player_metrics[0] 

                    # loop through hardware, settings, etc
                    for group_name in blueprint.keys():
                        
                        # check the actual numbers inside
                        for metric_name, metric_value in blueprint[group_name].items():
                            
                            # if it's a number we just average it normally
                            if isinstance(metric_value, (int, float)):
                                total = sum(s[group_name][metric_name] for s in player_metrics)
                                category_averages[category_name][group_name][metric_name] = total / len(player_metrics)
                                
                            # if it's text like resolution, just pick the one they use the most
                            elif isinstance(metric_value, str):
                                all_strings = [s[group_name][metric_name] for s in player_metrics]
                                most_common = Counter(all_strings).most_common(1)[0][0]
                                category_averages[category_name][group_name][metric_name] = most_common

            average_energy = player_energy / num_categories if num_categories > 0 else 0
            
            valid_players.append({
                "steam_id": Steam_ID,
                "country": player_data["country"],
                "is_subscribed": player_data["is_subscribed"],
                "rank": get_overall_rank(average_energy, energy_map),
                "category_metrics": category_averages
            })

    print("\n Dumping JSON data")
    
    # make sure ranks are sorted highest to lowest
    sorted_ranks_desc = [r[0] for r in sorted(energy_map.items(), key=lambda item: item[1], reverse=True)]
    RANK_ORDER = sorted_ranks_desc + ["Unranked"]
    
    rank_stats = {
        rank: {
            "count": 0,
            "country_tally": Counter(),
            "category_totals": {} 
        } for rank in RANK_ORDER
    }
    
    # go through all players and add up their stats
    for p in valid_players:
        r = p["rank"]
        rank_stats[r]["count"] += 1
        
        if p["country"] != "N/A":
            rank_stats[r]["country_tally"][p["country"]] += 1
            
        # add up all the metrics for the whole group
        for cat_name, groups in p["category_metrics"].items():
            
            if cat_name not in rank_stats[r]["category_totals"]:
                rank_stats[r]["category_totals"][cat_name] = {}
                
            for group_name, metrics in groups.items():
                
                if group_name not in rank_stats[r]["category_totals"][cat_name]:
                    rank_stats[r]["category_totals"][cat_name][group_name] = {}
                    
                for metric_name, metric_value in metrics.items():
                    
                    if metric_name not in rank_stats[r]["category_totals"][cat_name][group_name]:
                        rank_stats[r]["category_totals"][cat_name][group_name][metric_name] = {"sum": 0, "count": 0, "strings": []}
                    
                    tracker = rank_stats[r]["category_totals"][cat_name][group_name][metric_name]
                    
                    if isinstance(metric_value, (int, float)):
                        tracker["sum"] += metric_value
                        tracker["count"] += 1
                    elif isinstance(metric_value, str):
                        tracker["strings"].append(metric_value)

    # do the final division to get the real averages
    final_output = []
    total_valid_players = len(valid_players)
    cumulative_count = total_valid_players 
    
    for rank in RANK_ORDER:
        data = rank_stats[rank]
        count = data["count"]
        
        # figure out the country percentages
        top_country = "N/A"
        country_breakdown = {}
        total_countries = sum(data["country_tally"].values()) 
        
        if total_countries > 0:
            top_country = data["country_tally"].most_common(1)[0][0]
            for country_code, country_count in data["country_tally"].items():
                percentage = (country_count / total_countries) * 100
                country_breakdown[country_code] = round(percentage, 1)
                
        # get the final category averages
        category_stats_final = {}
        for cat_name, groups in data["category_totals"].items():
            category_stats_final[cat_name] = {}
            for group_name, metrics in groups.items():
                category_stats_final[cat_name][group_name] = {}
                for metric_name, tracker in metrics.items():
                    
                    if tracker["count"] > 0:
                        decimals = 3 if metric_name == "ttk" else 1
                        category_stats_final[cat_name][group_name][metric_name] = round(tracker["sum"] / tracker["count"], decimals)
                        
                    elif len(tracker["strings"]) > 0:
                        most_common = Counter(tracker["strings"]).most_common(1)[0][0]
                        category_stats_final[cat_name][group_name][metric_name] = most_common
            
        percent_at_above = (cumulative_count / total_valid_players) * 100 if total_valid_players > 0 else 0

        final_output.append({
            "rank": rank,
            "count": count,
            "percentAtAbove": round(percent_at_above, 2),
            "demographics": {
                "topCountry": top_country,
                "countryBreakdownPercent": country_breakdown
            },
            "categoryStats": category_stats_final
        })
        
        cumulative_count -= count 

    # save it all to json
    with open("Example_Data.json", "w+") as f:
        json.dump(final_output, f, indent=4)
        
    print("Successfully generated example data")
    
    # TODO
    # Energy Calculations (Use dynamic extrapoloation to ensure smooth transition from ranks of different tiers)
    # Transform data into useable format (Merge scores of same tiers etc.)
    # Filter out players who haven't gotten energy in atleast one sub-category per category

Run_Scraper()