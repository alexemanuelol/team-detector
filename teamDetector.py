#!/usr/bin/env python3

description =\
"""
Team detection program for games on Battlemetrics and Steam. The program goes
through the player list on the battlemetrics server page and saves all player
names in an array. Then it goes through the Steam friend list of the player
you want to inspect and compares the friend list names with the Battlemetrics
player array to find out which friends are currently on the server. If the
program found any matches, it will then continue to go through the friend list
of those friends and so on. What you end up with is a table of all the players
that might be part of the same team as the player you provided the Steam
Profile. It will also create a .html file that visualize the friends network
to see who is friends with who etc...
"""

import re
import argparse
import requests
import networkx as nx
from pyvis.network import Network
import config
import json
import datetime

def main():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-b', type=str, required=True, help='Battlemetrics Page for the Server.')
    parser.add_argument('-s', type=str, required=True, help='Steam page of the person you want to inspect.')
    args = parser.parse_args()

    G = nx.Graph()

    battlemetricsPlayers = get_all_players()
    #battlemetricsPlayers = get_online_players(args.b)
    ## if get_online__players is used instead, there is no need for a battlemetrics api key.

    initialFriendList = get_friend_list(args.s)
    friends = { initialFriendList['steamId']: initialFriendList['name']}
    leftToCheck = compare_players(battlemetricsPlayers, initialFriendList['friends'])
    for friend in leftToCheck:
        G.add_edges_from([(initialFriendList['name'], friend[1])])

    while True:
        if len(leftToCheck) == 0:
            break

        newLeft = []
        for steamId, name in leftToCheck:
            friendList = get_friend_list(f'https://steamcommunity.com/profiles/{steamId}/friends')
            friends[friendList['steamId']] = friendList['name']
            for steamIdC, nameC in compare_players(battlemetricsPlayers, friendList['friends']):
                G.add_edges_from([(friendList['name'], nameC)])
                if steamIdC not in friends and not any(steamIdC in x for x in newLeft):
                    newLeft.append([steamIdC, nameC])

        leftToCheck = newLeft

    nt = Network('2000px', '2000px')
    nt.from_nx(G)
    nt.repulsion(damping=1)
    nt.show('team_network.html')

    print('Team Detector Result:\n')
    print('Name:'.ljust(34) + 'SteamID:'.ljust(19) + 'Link:')

    for steamId, name in friends.items():
        print(f'{name}'.ljust(34) + f'{steamId}'.ljust(19) + f'https://steamcommunity.com/profiles/{steamId}')

def scrape(url):
    try:
        page = requests.get(url)
        return page.text
    except:
        print(f'Could not scrape: {url}')
        return False

def get_online_players(url):
    players = []
    server_id = re.findall(r"(?<=https:\/\/www\.battlemetrics\.com\/servers\/rust\/)\d+", url)
    page = requests.get(f"https://api.battlemetrics.com/servers/{server_id[0]}?include=player")
    resp = page.json()
    for p_info in resp["included"]:
        players.append(p_info["attributes"]["name"])
        
    return players

def get_all_players():
    temp_start = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(30)
    start = temp_start.isoformat().replace("+00:00", "Z")
    stop = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    
    params = {
        "start":start,
        "stop":stop,
        "include":"player",
        "access_token": config.bm_api_key
    }
    
    p_list = []
    
    print("Requesting data from battlemetrics, this may take a while.")
    resp = requests.get("https://api.battlemetrics.com/servers/16636043/relationships/sessions", params=params)
    
    data = resp.json()
    for session in data['data']:
        player = session["attributes"]["name"]
        if player not in p_list:
            p_list.append(player)
    return p_list

def get_friend_list(url):
    if not 'friends' in url:
        url += '/friends'

    content = scrape(url)
    if content == False:
        print('Could not scrape friend list page')
        exit()

    regex = r'<meta property="og:title" content="(.+?)">'
    name = re.findall(regex, content)[0]
    regex = r',"steamid":"(.+?)",'
    steamId = re.findall(regex, content)[0]
    regex = r'data-steamid="(.+?)".*?<div class="friend_block_content">(.+?)<br>'
    friends = re.findall(regex, content, re.MULTILINE|re.S)

    return {"name": name, "steamId": steamId, "friends": friends}

def compare_players(battlemetricsPlayers, friendList):
    players = []
    for steamId, name in friendList:
        if name in battlemetricsPlayers:
            players.append([steamId, name])

    return players


if __name__ == '__main__':
    main()