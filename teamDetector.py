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

from pyvis.network import Network
import argparse
import json
import networkx as nx
import os
import re
import requests

JSON_FILE = 'teamDetectorLatest.json'

def request(url):
    try:
        page = requests.get(url)
        return page.text
    except:
        print(f'Could not request: {url}')
        return False

def get_battlemetrics_players(url):
    serverId = re.findall(r'(\d+)$', url)
    if len(serverId) == 0:
        print('Could not find serverId in battlemetrics URL.')
        exit()
    serverId = serverId[0]
    url = f'https://api.battlemetrics.com/servers/{serverId}?include=player'

    content = request(url)
    if content == False:
        print('Could not Request Battlemetrics Server Page.')
        exit()
    content = json.loads(content)

    players = []
    for player in content['included']:
        players.append(player['attributes']['name'])

    return players

def get_friend_list(url):
    if not 'friends' in url:
        url += '/friends'

    content = request(url)
    if content == False:
        print('Could not request friend list page')
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

def main():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-b', type=str, required=False, help='Battlemetrics Page for the Server.')
    parser.add_argument('-s', type=str, required=False, help='Steam page of the person you want to inspect.')
    args = parser.parse_args()

    G = nx.Graph()

    battlemetrics_url = args.b
    steam_url = args.s

    if os.path.isfile(JSON_FILE) and os.access(JSON_FILE, os.R_OK):
        with open(JSON_FILE, 'r') as f:
            jsonFile = json.load(f)
            if battlemetrics_url == None:
                if 'battlemetrics_url' not in jsonFile:
                    print('Battlemetrics URL missing.')
                    exit()
                battlemetrics_url = jsonFile['battlemetrics_url']
            if steam_url == None:
                if 'steam_url' not in jsonFile:
                    print('Steam URL missing.')
                    exit()
                steam_url = jsonFile['steam_url']
    else:
        with open(JSON_FILE, 'w') as f:
            f.write(json.dumps({}))

        if battlemetrics_url == None or steam_url == None:
            print('Battlemetrics or Steam URL is missing.')
            exit()

    battlemetricsPlayers = get_battlemetrics_players(battlemetrics_url)

    initialFriendList = get_friend_list(steam_url)
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

    jsonFile = None
    with open(JSON_FILE, 'r') as f:
        jsonFile = json.load(f)
        jsonFile['battlemetrics_url'] = battlemetrics_url
        jsonFile['steam_url'] = steam_url

    with open(JSON_FILE, 'w') as f:
        json.dump(jsonFile, f)


if __name__ == '__main__':
    main()