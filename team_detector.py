#!/usr/bin/env python3

description =\
"""
Team detection program for games on BattleMetrics and Steam. The program goes through the player list on the
BattleMetrics server page and saves all player names in an array. Then it goes through the Steam profile of the player
you want to inspect and compares the friend list names and profile comments with the BattleMetrics player array to
find out which friends are currently on the server. If the program found any matches, it will then continue to go
through the friend list of those friends and so on. What you end up with is a table of all the players that might be
part of the same team as the player you provided the Steam Profile. It will also create a .html file that visualize the
friends network to see who is friends with who etc...
"""

from pyvis.network import Network

import argparse
import json
import networkx as nx
import os
import re
import requests
import sys

JSON_FILE = 'team_detector.json'
RECURSIVE_DEPTH = 5
COMMENT_PAGES = 1

class TeamDetector:

    def __init__(self, debug: bool = False, recursive_depth: int = 5, search_comments: bool = False,
                 search_comments_max_pages: int = 1):
        """
        Initializes the TeamDetector instance.

        Args:
            debug (bool): Whether to enable debug mode.
            recursive_depth (int): How deep can the recursive search go?
            search_comments (bool): Whether to search for comments on Steam profiles.
            search_comments_max_pages (int): Maximum number of pages to search for comments.
        """
        self.debug = debug
        self.recursive_depth = recursive_depth
        self.search_comments = search_comments
        self.search_comments_max_pages = search_comments_max_pages

        self.steam_profiles = dict()                    # steam_id as key and steam profile content as value
        self.steam_profiles_friends = dict()            # steam_id as key and steam friends list as value
        self.custom_id_translation_table = dict()       # custom_id as key and steam_id as value


    ##################################################
    #   Private methods
    ##################################################

    def __get_url_battlemetrics(self, server_id: str) -> str:
        """
        Generate the URL for retrieving information about a server from the BattleMetrics API.

        Args:
            server_id (str): The ID of the server to retrieve information for.

        Returns:
            str: The URL for retrieving server information from the BattleMetrics API.
        """
        return f'https://api.battlemetrics.com/servers/{server_id}?include=player'


    def __get_url_steam_profile_by_steam_id(self, steam_id: str) -> str:
        """
        Generate the URL for a Steam profile based on the provided Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            str: The URL for the Steam profile.
        """
        return f'https://steamcommunity.com/profiles/{steam_id}/?l=english'


    def __get_url_steam_profile_by_custom_id(self, custom_id: str) -> str:
        """
        Generate the URL for a Steam profile based on the provided Custom ID.

        Args:
            custom_id (str): The Custom ID of the profile.

        Returns:
            str: The URL for the Steam profile.
        """
        return f'https://steamcommunity.com/id/{custom_id}/?l=english'


    def __get_url_steam_profile_friends_by_steam_id(self, steam_id: str) -> str:
        """
        Generate the URL for the friends list of a Steam profile based on the provided Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            str: The URL for the friends list of the Steam profile.
        """
        return f'https://steamcommunity.com/profiles/{steam_id}/friends/?l=english'


    def __get_url_steam_profile_friends_by_custom_id(self, custom_id: str) -> str:
        """
        Generate the URL for the friends list of a Steam profile based on the provided Custom ID.

        Args:
            custom_id (str): The Custom ID of the profile.

        Returns:
            str: The URL for the friends list of the Steam profile.
        """
        return f'https://steamcommunity.com/id/{custom_id}/friends/?l=english'


    def __get_url_steam_profile_comments_page_by_steam_id(self, steam_id: str, page: int = 1) -> str:
        """
        Generate the URL for a specific page of comments on a Steam profile based on the provided Steam ID and page
        number.

        Args:
            steam_id (str): The Steam ID of the profile.
            page (int): The page number of comments. Defaults to 1.

        Returns:
            str: The URL for the specified page of comments on the Steam profile.
        """
        return f'https://steamcommunity.com/profiles/{steam_id}/allcomments/?l=english&ctp={page}'


    def __get_url_steam_profile_comments_page_by_custom_id(self, custom_id: str, page: int = 1) -> str:
        """
        Generate the URL for a specific page of comments on a Steam profile based on the provided Custom ID and page
        number.

        Args:
            custom_id (str): The Custom ID of the profile.
            page (int): The page number of comments. Defaults to 1.

        Returns:
            str: The URL for the specified page of comments on the Steam profile.
        """
        return f'https://steamcommunity.com/id/{custom_id}/allcomments/?l=english&ctp={page}'


    def __print(self, text: str):
        """
        Print the provided text if debug mode is enabled.

        Args:
            text (str): The text to be printed.
        """
        if self.debug: print(text)


    def __request(self, url: str) -> str:
        """
        Make a GET request to the specified URL and return the response text.

        Args:
            url (str): The URL to make the request to.

        Returns:
            str: The text content of the response.

        Raises:
            ValueError: If the URL is empty or None.
            requests.exceptions.RequestException: If there's an error during the request.
        """
        if not url:
            raise ValueError(f'URL cannot be empty or None. URL: {url}')

        try:
            self.__print(f'Requesting: {url}')
            response = requests.get(url)
            response.raise_for_status()  # Raises an HTTPError if the response status is not successful
            return response.text
        except requests.exceptions.RequestException as e:
            print(f'Could not request: {url}. Error: {e}')
            return ''


    def __is_steam_profile_cached_by_steam_id(self, steam_id: str) -> bool:
        """
        Check if a Steam profile is cached in the instance by its Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile to check.

        Returns:
            bool: True if the profile is cached, False otherwise.
        """
        value = True if steam_id in self.steam_profiles else False
        self.__print(f'__is_steam_profile_cached_by_steam_id(steam_id:{steam_id}) -> bool:{value}')
        return value


    def __is_steam_profile_cached_by_custom_id(self, custom_id: str) -> bool:
        """
        Check if a Steam profile is cached in the instance by its Custom ID.

        Args:
            custom_id (str): The Custom ID of the profile to check.

        Returns:
            bool: True if the profile is cached, False otherwise.
        """
        if custom_id in self.custom_id_translation_table:
            if self.custom_id_translation_table[custom_id] in self.steam_profiles:
                self.__print(f'__is_steam_profile_cached_by_custom_id(custom_id:{custom_id}) -> bool:{True}')
                return True

        self.__print(f'__is_steam_profile_cached_by_custom_id(custom_id:{custom_id}) -> bool:{False}')
        return False


    def __is_steam_profile_friends_cached_by_steam_id(self, steam_id: str) -> bool:
        """
        Check if a Steam profile friends list is cached in the instance by its Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile friends list to check.

        Returns:
            bool: True if the profile friends list is cached, False otherwise.
        """
        value = True if steam_id in self.steam_profiles_friends else False
        self.__print(f'__is_steam_profile_friends_cached_by_steam_id(steam_id:{steam_id}) -> bool:{value}')
        return value


    def __get_steam_profile_content_by_steam_id(self, steam_id: str) -> str:
        """
        Retrieve the content of a Steam profile page based on the provided Steam ID.

        If the content is already cached in the instance, it will be retrieved from the cache.
        Otherwise, it will be fetched from the Steam API, cached, and returned.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            str: The content of the Steam profile page.
        """
        try:
            self.__print(f'__get_steam_profile_content_by_steam_id(steam_id:{steam_id})')

            content = None
            if self.__is_steam_profile_cached_by_steam_id(steam_id):
                content = self.steam_profiles[steam_id]
            else:
                content = self.__request(self.__get_url_steam_profile_by_steam_id(steam_id))
                if content == '': exit()
                self.steam_profiles[steam_id] = content

            return content
        except Exception as e:
            sys.exit(e)


    def __get_steam_profile_content_by_custom_id(self, custom_id: str) -> str:
        """
        Retrieve the content of a Steam profile page based on the provided Custom ID.

        If the content is already cached in the instance, it will be retrieved from the cache.
        Otherwise, it will be fetched from the Steam API using the provided Custom ID, and the fetched
        content will be cached along with its associated Steam ID.

        Args:
            custom_id (str): The Custom ID of the profile.

        Returns:
            str: The content of the Steam profile page.
        """
        try:
            self.__print(f'__get_steam_profile_content_by_custom_id(custom_id:{custom_id})')

            content = None
            if self.__is_steam_profile_cached_by_custom_id(custom_id):
                content = self.steam_profiles[self.custom_id_translation_table[custom_id]]
            else:
                content = self.__request(self.__get_url_steam_profile_by_custom_id(custom_id))
                if content == '': exit()
                steam_id = self.__get_steam_profile_steam_id_by_content(content)
                if steam_id == '': exit('Steam ID was empty.')
                self.custom_id_translation_table[custom_id] = steam_id
                if not self.__is_steam_profile_cached_by_steam_id(steam_id):
                    self.steam_profiles[steam_id] = content

            return content
        except Exception as e:
            sys.exit(e)


    def __get_steam_profile_friends_content_by_steam_id(self, steam_id: str) -> str:
        """
        Retrieve the content of a Steam profile friends page based on the provided Steam ID.

        If the content is already cached in the instance, it will be retrieved from the cache.
        Otherwise, it will be fetched from the Steam API, cached, and returned.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            str: The content of the Steam profile friends page.
        """
        try:
            self.__print(f'__get_steam_profile_friends_content_by_steam_id(steam_id:{steam_id})')

            content = None
            if self.__is_steam_profile_friends_cached_by_steam_id(steam_id):
                content = self.steam_profiles_friends[steam_id]
            else:
                content = self.__request(self.__get_url_steam_profile_friends_by_steam_id(steam_id))
                if content == '': exit()
                self.steam_profiles_friends[steam_id] = content

            return content
        except Exception as e:
            sys.exit(e)


    def __get_steam_profile_comments_page_content_by_steam_id(self, steam_id: str, page: int = 1) -> str:
        """
        Retrieve the content of a specific page of comments on a Steam profile based on the provided Steam ID and page
        number.

        Args:
            steam_id (str): The Steam ID of the profile.
            page (int): The page number of comments. Defaults to 1.

        Returns:
            str: The content of the specified page of comments on the Steam profile.
        """
        try:
            self.__print(f'__get_steam_profile_comments_page_content_by_steam_id(steam_id:{steam_id}, page:{page})')

            content = self.__request(self.__get_url_steam_profile_comments_page_by_steam_id(steam_id, page))
            if content == '': exit()

            return content
        except Exception as e:
            sys.exit(e)


    def __get_steam_profile_steam_id_by_content(self, steam_profile_content: str) -> str:
        """
        Extract the Steam ID of a Steam profile from the content of the profile page.

        Args:
            steam_profile_content (str): The content of the Steam profile page.

        Returns:
            str: The Steam ID of the Steam profile.
        """
        regex = r',"steamid":"(.*?)",'
        steam_id = re.findall(regex, steam_profile_content, re.MULTILINE|re.S)
        steam_id = '' if len(steam_id) == 0 else steam_id[0]

        self.__print(f'__get_steam_profile_steam_id_by_content(content) -> steam_id:{steam_id}')
        return steam_id


    def __get_steam_profile_custom_id_by_content(self, steam_profile_content: str) -> str:
        """
        Extract the Custom ID of a Steam profile from the content of the profile page.

        Args:
            steam_profile_content (str): The content of the Steam profile page.

        Returns:
            str: The Custom ID of the Steam profile if it exist, else empty str.
        """
        regex = r'g_rgProfileData = {"url":"https:\/\/steamcommunity.com\/id\/(.*)\/'
        custom_id = re.findall(regex, steam_profile_content, re.MULTILINE|re.S)
        custom_id = '' if len(custom_id) == 0 else custom_id[0]

        self.__print(f'__get_steam_profile_custom_id_by_content(content) -> custom_id:{custom_id}')
        return custom_id


    def __remove_duplicates(self, people: list) -> list:
        """
        Removes duplicate entries from a list of people dictionaries based on steam_id or custom_id.

        Args:
            people (list): A list of dictionaries representing people, each with 'steam_id' and/or 'custom_id'.

        Returns:
            list: A list with duplicate entries removed based on 'steam_id' or 'custom_id'.
        """
        temp = []
        for item in people:
            exist = False
            for i in temp:
                if item['steam_id'] != None and i['steam_id'] == item['steam_id']:
                    exist = True
                    break

                if item['custom_id'] != None and i['custom_id'] == item['custom_id']:
                    exist = True
                    break

            if not exist:
                temp.append(item)

        self.__print(f'__remove_duplicates(List[people:{len(people)}]) -> List[temp:{len(temp)}]')
        return temp


    def __remove_self_from_people(self, profile_steam_id: str, profile_custom_id: str, people) -> list:
        """
        Removes the profile identified by profile_steam_id or profile_custom_id from the list of people.

        Args:
            profile_steam_id (str): The Steam ID of the profile to be removed.
            profile_custom_id (str): The custom ID of the profile to be removed.
            people (list): A list of dictionaries representing people, each with 'steam_id' and/or 'custom_id'.

        Returns:
            list: A list with the profile removed.
        """
        temp = []
        for item in people:
            if item['steam_id'] == profile_steam_id or item['custom_id'] == profile_custom_id:
                continue
            temp.append(item)

        self.__print(f'__remove_self_from_people(profile_steam_id:{profile_steam_id}, profile_custom_id:' +
                     f'{profile_custom_id}, List[people:{len(people)}]) -> List[temp:{len(temp)}]')
        return temp


    def __compare_people_to_battlemetrics_players(self, people: list, battlemetrics_players: list) -> list:
        """
        Compares the list of people with the list of BattleMetrics players and returns those that match by name.

        Args:
            people (list): A list of dictionaries representing people.
            battlemetrics_players (list): A list of names representing BattleMetrics players.

        Returns:
            list: A list of dictionaries containing people who match the names in the BattleMetrics players list.
        """
        temp = []
        for item in people:
            if item['name'] in battlemetrics_players:
                temp.append(item)

        self.__print(f'__compare_people_to_battlemetrics_players(List[people:{len(people)}], ' +
                     f'List[battlemetrics_players:{len(battlemetrics_players)}]) -> List[temp:{len(temp)}]')
        return temp


    def __compare_people_to_already_found_players(self, people: list, found_players: list) -> list:
        """
        Compares the list of people with the already found players and returns those that are not already in the found
        players list.

        Args:
            people (list): A list of dictionaries representing people.
            found_players (list): A list of dictionaries representing already found players.

        Returns:
            list: A list of dictionaries containing people who are not already in the found players list.
        """
        temp = []
        for item in people:
            exist = False
            for i in found_players:
                if item['steam_id'] != None and item['steam_id'] == i['steam_id']:
                    exist = True
                    break

                if item['custom_id'] != None and item['custom_id'] == i['custom_id']:
                    exist = True
                    break

            if not exist:
                temp.append(item)

        self.__print(f'__compare_people_to_already_found_players(List[people:{len(people)}], ' +
                     f'List[found_players:{len(found_players)}]) -> List[temp:{len(temp)}]')
        return temp


    ##################################################
    #   Public methods
    ##################################################

    def start_search(self, server_id: str, steam_ids: list):
        """
        Starts the search for interconnected Steam profiles based on provided Steam IDs.

        Args:
            server_id (str): The ID of the server.
            steam_ids (list): A list of Steam IDs to start the search from.
        """
        self.__print(f'start_search(server_id:{server_id}, steam_ids:{len(steam_ids)})')

        G = nx.Graph()

        battlemetrics_players = self.get_battlemetrics_players(server_id)
        found_players = []
        searched_steam_ids = []
        recursives = 0
        peoples_connections = dict()

        def recursive_search(profile_steam_id: str, recursive_depth: int = 0):
            """
            Recursively searches for interconnected Steam profiles.

            Args:
                profile_steam_id (str): The Steam ID of the profile to start the search from.
                recursive_depth (int): The current recursive depth.
            """
            if recursive_depth == self.recursive_depth:
                return

            nonlocal recursives
            self.__print(f'start_search:recursive_search(profile_steam_id:{profile_steam_id}, ' +
                         f'recursive_depth:{recursive_depth})')

            if profile_steam_id in searched_steam_ids:
                self.__print(f'start_search:recursive_search(profile_steam_id:{profile_steam_id}, ' +
                             f'recursive_depth:{recursive_depth}) -> Already searched')
                return

            recursives += 1

            searched_steam_ids.append(profile_steam_id)
            people = []

            profile_name = self.get_steam_profile_name(profile_steam_id)
            profile_custom_id = self.get_steam_profile_custom_id_by_steam_id(profile_steam_id)

            found_players.append({
                'steam_id': profile_steam_id,
                'custom_id': profile_custom_id,
                'name': profile_name
            })

            # Append friends list to people
            if self.is_steam_profile_friends_public(profile_steam_id):
                people += self.get_steam_profile_friends(profile_steam_id)

            # Append comment authors to people
            if self.search_comments and self.search_comments_max_pages > 0 and \
                self.is_steam_profile_comments_public(profile_steam_id):
                number_of_comments = self.get_number_of_comments(profile_steam_id)
                for i in range(1, self.search_comments_max_pages + 1):
                    if number_of_comments <= 0: break
                    number_of_page_comments, authors = self.get_steam_profile_comments_page_authors(profile_steam_id, i)
                    number_of_comments -= number_of_page_comments
                    people += authors

            peoples_connections[profile_steam_id] = (profile_name, profile_custom_id, people)

            people = self.__remove_duplicates(people)
            people = self.__remove_self_from_people(profile_steam_id, profile_custom_id, people)

            people = self.__compare_people_to_battlemetrics_players(people, battlemetrics_players)

            # Create node connections
            for item in people:
                G.add_edges_from([(profile_name, item['name'])])

            people = self.__compare_people_to_already_found_players(people, found_players)

            for item in people:
                steam_id = item['steam_id']
                if steam_id == None:
                    steam_id = self.get_steam_profile_steam_id_by_custom_id(item['custom_id'])
                recursive_search(steam_id, recursive_depth + 1)

            if recursives == 1:
                G.add_node(profile_name)

        for id in steam_ids:
            recursive_search(id)
            recursives = 0

        for steam_id_outer, (name_outer, custom_id_outer, connections_outer) in peoples_connections.items():
            for steam_id_inner, (name_inner, custom_id_inner, connections_inner) in peoples_connections.items():
                if steam_id_outer == steam_id_inner : continue
                if custom_id_outer != '' and custom_id_outer == custom_id_inner: continue

                steam_id_in_connections = any(steam_id_outer == connection['steam_id'] for connection in
                                              connections_inner)
                custom_id_in_connections = any(custom_id_outer != '' and custom_id_outer == connection['custom_id']
                                               for connection in connections_inner)

                if steam_id_in_connections or custom_id_in_connections:
                    G.add_edges_from([(name_outer, name_inner)])

        print('\nTeam Detector Network written to:')

        nt = Network('2000px', '2000px')
        nt.from_nx(G)
        nt.repulsion(damping=1)
        nt.show('team_network.html', notebook=False)

        print('\nTeam Detector Result:\n')
        print('Name:'.ljust(34) + 'SteamID:'.ljust(19) + 'Link:')

        for player in found_players:
            print(f'{player['name']}'.ljust(34) + f'{player['steam_id']}'.ljust(19) +
                  self.__get_url_steam_profile_by_steam_id(player['steam_id']))


    def get_battlemetrics_players(self, server_id: str) -> list:
        """
        Retrieve a list of players currently connected to a server from the BattleMetrics API.

        Args:
            server_id (str): The ID of the server to retrieve player information for.

        Returns:
            list: A list of player names currently connected to the server.
        """
        try:
            self.__print(f'get_battlemetrics_players(server_id:{server_id})')

            content = self.__request(self.__get_url_battlemetrics(server_id))
            if content == '': exit()
            content = json.loads(content)

            players = []
            for player in content['included']:
                players.append(player['attributes']['name'])

            self.__print(f'get_battlemetrics_players(server_id:{server_id}) -> List[players:{len(players)}]')
            return players
        except Exception as e:
            sys.exit(e)


    def get_steam_profile_steam_id_by_custom_id(self, custom_id: str) -> str:
        """
        Retrieve the Steam ID associated with a Custom ID.

        Args:
            custom_id (str): The Custom ID of the profile.

        Returns:
            str: The Steam ID associated with the Custom ID.
        """
        self.__print(f'get_steam_profile_steam_id_by_custom_id(custom_id:{custom_id})')

        if custom_id in self.custom_id_translation_table:
            steam_id = self.custom_id_translation_table[custom_id]
            self.__print(f'get_steam_profile_steam_id_by_custom_id(custom_id:{custom_id}) -> steam_id:{steam_id}')
            return steam_id

        content = self.__get_steam_profile_content_by_custom_id(custom_id)
        steam_id = self.__get_steam_profile_steam_id_by_content(content)

        self.__print(f'get_steam_profile_steam_id_by_custom_id(custom_id:{custom_id}) -> steam_id:{steam_id}')
        return steam_id


    def get_steam_profile_custom_id_by_steam_id(self, steam_id: str) -> str:
        """
        Retrieve the Custom ID associated with a Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            str: The Custom ID associated with the Steam ID.
        """
        self.__print(f'get_steam_profile_custom_id_by_steam_id(steam_id:{steam_id})')

        for key, value in self.custom_id_translation_table.items():
            if steam_id == value:
                self.__print(f'get_steam_profile_custom_id_by_steam_id(steam_id:{steam_id}) -> custom_id:{key}')
                return key

        content = self.__get_steam_profile_content_by_steam_id(steam_id)
        custom_id = self.__get_steam_profile_custom_id_by_content(content)
        self.__print(f'get_steam_profile_custom_id_by_steam_id(steam_id:{steam_id}) -> custom_id:{custom_id}')
        return custom_id


    def get_steam_profile_name(self, steam_id: str) -> str:
        """
        Retrieve the name of a Steam profile by its Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            str: The name of the Steam profile.
        """
        self.__print(f'get_steam_profile_name(steam_id:{steam_id})')

        content = self.__get_steam_profile_content_by_steam_id(steam_id)
        regex = r'<div class="persona_name" style="font-size: 24px;">.*?<span class="actual_persona_name">(.*?)<\/span>'
        name = re.findall(regex, content, re.MULTILINE|re.S)
        name = '' if len(name) == 0 else name[0]
        self.__print(f'get_steam_profile_name(steam_id:{steam_id}) -> name:{name}')
        return name


    def is_steam_profile_friends_public(self, steam_id: str) -> bool:
        """
        Check if a Steam profile's friends list is public based on the content of the profile page.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            bool: True if the friends list is public, False otherwise.
        """
        self.__print(f'is_steam_profile_friends_public(steam_id:{steam_id})')

        content = self.__get_steam_profile_content_by_steam_id(steam_id)
        content_no_space = re.sub(r'\s+', '', content)
        value = '/friends/"><spanclass="count_link_label">friends</span>' in content_no_space.lower()
        self.__print(f'is_steam_profile_friends_public(steam_id:{steam_id}) -> bool:{value}')
        return value


    def is_steam_profile_comments_public(self, steam_id: str) -> bool:
        """
        Check if a Steam profile's comments section is public based on the content of the profile page.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            bool: True if the comments section is public, False otherwise.
        """
        self.__print(f'is_steam_profile_comments_public(steam_id:{steam_id})')

        content = self.__get_steam_profile_content_by_steam_id(steam_id)
        content_no_space = re.sub(r'\s+', '', content)
        value = '<spanclass="commentthread_header_label">comments</span>' in content_no_space.lower()
        self.__print(f'is_steam_profile_comments_public(steam_id:{steam_id}) -> bool:{value}')
        return value


    def get_number_of_comments(self, steam_id: str) -> int:
        """
        Get the number of comments on a Steam profile based on the provided Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            int: The number of comments on the Steam profile.
        """
        self.__print(f'get_number_of_comments(steam_id:{steam_id})')

        if not self.is_steam_profile_comments_public(steam_id):
            self.__print(f'get_number_of_comments(steam_id:{steam_id}) -> int:0')
            return 0

        content = self.__get_steam_profile_content_by_steam_id(steam_id)
        content_no_space = re.sub(r'\s+', '', content)
        matches = re.findall(r'<spanid="commentthread_profile_\d+_totalcount">(.*?)<\/span>', content_no_space.lower())

        try:
            number = 0 if len(matches) == 0 else int(re.sub(r'[^0-9]', '', matches[0]))
            self.__print(f'get_number_of_comments(steam_id:{steam_id}) -> int:{number}')
            return number
        except Exception as e:
            self.__print(f'get_number_of_comments(steam_id:{steam_id}) -> int:0')
            return 0


    def get_steam_profile_friends(self, steam_id: str) -> list:
        """
        Retrieve the friends list of a Steam profile based on the provided Steam ID.

        Args:
            steam_id (str): The Steam ID of the profile.

        Returns:
            list: A list of dictionaries containing friend information such as steam_id, custom_id, name and type
            ('friends'/'comments').
        """
        self.__print(f'get_steam_profile_friends(steam_id:{steam_id})')

        content = self.__get_steam_profile_friends_content_by_steam_id(steam_id)
        regex = r'data-steamid="(.+?)".*?href="https:\/\/steamcommunity.com\/(.+?)">.*?' + \
                r'<div class="friend_block_content">(.+?)<br>'
        matches = re.findall(regex, content, re.MULTILINE|re.S)

        friends = []
        for friend_steam_id, friend_custom_id, friend_name in matches:
            friend = dict()
            friend['steam_id'] = friend_steam_id

            custom_id = friend_custom_id.replace('id/', '') if friend_custom_id.startswith('id') else None
            if custom_id != None and custom_id not in self.custom_id_translation_table:
                self.custom_id_translation_table[custom_id] = friend_steam_id
            friend['custom_id'] = custom_id

            friend['name'] = friend_name
            friend['type'] = 'friends'
            friends.append(friend)

        self.__print(f'get_steam_profile_friends(steam_id:{steam_id}) -> List[friends:{len(friends)}]')
        return friends


    def get_steam_profile_comments_page_authors(self, steam_id: str, page: int = 1) -> tuple:
        """
        Retrieve the authors of comments on a specific page of a Steam profile based on the provided Steam ID and page number.

        Args:
            steam_id (str): The Steam ID of the profile.
            page (int): The page number of comments. Defaults to 1.

        Returns:
            tuple: A tuple containing the total number of comments read and a list of dictionaries containing comment
            author information such as steam_id, custom_id, name, and type ('comments' or 'friends').
        """
        self.__print(f'get_steam_profile_comments_page_authors(steam_id:{steam_id}, page:{page})')

        content = self.__get_steam_profile_comments_page_content_by_steam_id(steam_id, page)

        regex = r'hoverunderline commentthread_author_link" ' \
                r'href="https://steamcommunity.com/profiles/(.*?)".*?<bdi>(.*?)<\/bdi>'
        comments_authors_steam_id = re.findall(regex, content, re.MULTILINE|re.S)

        regex = r'hoverunderline commentthread_author_link" ' \
                r'href="https://steamcommunity.com/id/(.*?)".*?<bdi>(.*?)<\/bdi>'
        comments_authors_custom_id = re.findall(regex, content, re.MULTILINE|re.S)

        total_read_comments = len(comments_authors_steam_id) + len(comments_authors_custom_id)

        comments_page_authors = []
        for author_steam_id, author_name in comments_authors_steam_id:
            if any(author['steam_id'] == author_steam_id for author in comments_page_authors):
                continue

            author = dict()
            author['steam_id'] = author_steam_id
            author['custom_id'] = None
            author['name'] = author_name
            author['type'] = 'comments'
            comments_page_authors.append(author)

        for author_custom_id, author_name in comments_authors_custom_id:
            if any(author['custom_id'] == author_custom_id for author in comments_page_authors):
                continue

            author = dict()
            author['steam_id'] = None
            author['custom_id'] = author_custom_id
            author['name'] = author_name
            author['type'] = 'comments'
            comments_page_authors.append(author)

        self.__print(f'get_steam_profile_comments_page_authors(steam_id:{steam_id}, page:{page}) -> ' +
                     f'total_read_comments:{total_read_comments}, List[comments_page_authors:' +
                     f'{len(comments_page_authors)}]')
        return total_read_comments, comments_page_authors


def read_config() -> tuple[str, list[str]]:
    """
    Read configuration from a JSON file and return the BattleMetrics ID and Steam ID(s).

    Returns:
        Tuple[str, List[str]]: A tuple containing BattleMetrics ID (str) and Steam ID (List[str]).
    """
    battlemetrics_id = None
    steam_id = None

    if os.path.isfile(JSON_FILE) and os.access(JSON_FILE, os.R_OK):
        with open(JSON_FILE, 'r') as f:
            jsonFile = json.load(f)

            if 'battlemetrics_id' in jsonFile:
                battlemetrics_id = jsonFile['battlemetrics_id']

            if 'steam_id' in jsonFile:
                steam_id = jsonFile['steam_id']

    return battlemetrics_id, steam_id


def write_config(battlemetrics_id: str, steam_id: list) -> None:
    """
    Write BattleMetrics ID and Steam ID(s) to a JSON file.

    Args:
        battleMetrics_id (str): The BattleMetrics ID to be written to the config.
        steam_id (list): The Steam ID(s) to be written to the config.
    """
    with open(JSON_FILE, 'w') as f:
        jsonFile = dict()
        jsonFile['battlemetrics_id'] = battlemetrics_id
        jsonFile['steam_id'] = steam_id
        json.dump(jsonFile, f)


def main():
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-b', '--battlemetrics-id', type=str, required=False, help='BattleMetrics Server ID.')
    parser.add_argument('-s', '--steam-id', type=str, nargs='+', required=False,
                        help='SteamID(s) of the person(s) you want to inspect (Separated by space).')
    parser.add_argument('-r', '--recursive-depth', type=int, required=False,
                        help=f'How deep can the recursive search go? (Default {RECURSIVE_DEPTH}).')
    parser.add_argument('-c', '--comments', action='store_true', required=False,
                        help='Search through profile comments.')
    parser.add_argument('-p', '--comment-pages', type=int, required=False,
                        help='The number of comment pages to go through per profile (Default 1 page).')
    parser.add_argument('-d', '--debug', action='store_true', required=False, help='Enables debug print.')
    args = parser.parse_args()

    battlemetrics_id = args.battlemetrics_id
    steam_id = args.steam_id
    recursive_depth = RECURSIVE_DEPTH if args.recursive_depth == None else args.recursive_depth
    comments = args.comments
    comment_pages = COMMENT_PAGES if args.comment_pages == None else args.comment_pages
    debug = args.debug

    config_battlemetrics_id, config_steam_id = read_config()

    if battlemetrics_id == None:
        battlemetrics_id = config_battlemetrics_id
    if steam_id == None:
        steam_id = config_steam_id

    if battlemetrics_id == None or steam_id == None:
        sys.exit('BattleMetrics Server ID or Steam ID is not provided.')

    if debug:
        print('Running with the following arguments:')
        print(f' - Battlemetrics Server ID:     {battlemetrics_id}')
        print(f' - Steam ID(s):                 {steam_id}')
        print(f' - Recursive Depth:             {recursive_depth}')
        print(f' - Comments:                    {comments}')
        print(f' - Comment Pages:               {comment_pages}')
        print(f' - Debug:                       {debug}')
        print()

    td = TeamDetector(debug, recursive_depth, comments, comment_pages)
    td.start_search(battlemetrics_id, steam_id)

    write_config(battlemetrics_id, steam_id)


if __name__ == '__main__':
    main()