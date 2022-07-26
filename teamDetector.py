#!/usr/bin/env python3

import re
import argparse
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-b', type=str, required=True, help='Battlemetrics Page for the Rust Server.')
    parser.add_argument('-f', type=str, required=True, help='Friendlist of the person you want to inspect.')
    args = parser.parse_args()

    battlemetricsPlayers = get_battlemetrics_players(args.b)

    initialFriendlist = get_friendlist(args.f)
    friends = { initialFriendlist['steamId']: initialFriendlist['name']}
    leftToCheck = compare_players(battlemetricsPlayers, initialFriendlist['friends'])

    while True:
        if len(leftToCheck) == 0:
            break

        newLeft = []
        for steamId, name in leftToCheck:
            friendlist = get_friendlist(f'https://steamcommunity.com/profiles/{steamId}/friends')
            friends[friendlist['steamId']] = friendlist['name']
            for steamIdC, nameC in compare_players(battlemetricsPlayers, friendlist['friends']):
                if steamIdC not in friends and not any(steamIdC in x for x in newLeft):
                    newLeft.append([steamIdC, nameC])

        leftToCheck = newLeft

    for steamId, name in friends.items():
        print(f'{name}: {steamId}')

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

    regex = r'"steamid":"(.+?)","personaname":"(.+?)"'
    info = re.findall(regex, content)[0]
    steamId = info[0]
    name = info[1]
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