#!/usr/bin/env python3

description =\
"""
Team detection program for the game Rust. The program goes through the
friendlist of the player you provided and compares the friendlist with the
battlemetrics page for the Rust server you provided. If matches are found, the
program continues to go through their friendslists and compare with the
battlemetrics page players, ultimately creating a network of players that are
potentially in a team.
"""

import re
import argparse
import requests
import networkx as nx
from pyvis.network import Network

def main():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-b', type=str, required=True, help='Battlemetrics Page for the Rust Server.')
    parser.add_argument('-s', type=str, required=True, help='Steam page of the person you want to inspect.')
    args = parser.parse_args()

    G = nx.Graph()

    battlemetricsPlayers = get_battlemetrics_players(args.b)

    initialFriendlist = get_friendlist(args.s)
    friends = { initialFriendlist['steamId']: initialFriendlist['name']}
    leftToCheck = compare_players(battlemetricsPlayers, initialFriendlist['friends'])
    for friend in leftToCheck:
        G.add_edges_from([(initialFriendlist['name'], friend[1])])

    while True:
        if len(leftToCheck) == 0:
            break

        newLeft = []
        for steamId, name in leftToCheck:
            friendlist = get_friendlist(f'https://steamcommunity.com/profiles/{steamId}/friends')
            friends[friendlist['steamId']] = friendlist['name']
            for steamIdC, nameC in compare_players(battlemetricsPlayers, friendlist['friends']):
                G.add_edges_from([(friendlist['name'], nameC)])
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

def get_battlemetrics_players(url):
    content = scrape(url)
    if content == False:
        print('Could not scrape battlemetrics server Ppge')
        exit()

    regex = r'<a class="css-zwebxb" href="/players/\d+?">(.+?)</a>'
    players = re.findall(regex, content)
    if len(players) == 0:
        print('Could not match players on the battlemetrics page.')
        exit()

    return players

def get_friendlist(url):
    if not 'friends' in url:
        url += '/friends'

    content = scrape(url)
    if content == False:
        print('Could not scrape friendlist page')
        exit()
    regex = r'<meta property="og:title" content="(.+?)">'
    name = re.findall(regex, content)[0]
    regex = r',"steamid":"(.+?)",'
    steamId = re.findall(regex, content)[0]
    regex = r'data-steamid="(.+?)".*?<div class="friend_block_content">(.+?)<br>'
    friends = re.findall(regex, content, re.MULTILINE|re.S)

    return {"name": name, "steamId": steamId, "friends": friends}

def compare_players(battlemetricsPlayers, friendlist):
    players = []
    for steamId, name in friendlist:
        if name in battlemetricsPlayers:
            players.append([steamId, name])

    return players


if __name__ == '__main__':
    main()