from __future__ import division
from player import Player
from house import *
from utils import ScoreCounter, ordinal
from collections import defaultdict
from pprint import pprint
'''
LEAGUES
'''

class League(object):
    """League in Ascension Crossed Banners"""

    def __init__(self, name, game):
        super(League, self).__init__()
        self.name = name
        self.game = game

        for k, v in game.db['players'].iteritems():
            v['id'] = k

        self.players_raw = filter(self.filter_player, game.db['players'].values())
        
        self.votes = filter(self.filter_league, game.db['votes'].values())
        self.missions = filter(self.filter_league, game.db['missions'].values())
        self.intelligence = filter(self.filter_league, game.db['player_intelligence'].values())
        
        self.current_episode = game.most_recent_episode
        self.current_episode_score = {}
        
        self.players = self.init_players()
        self.roster_ids = self.collect_player_rosters_ids()
        self.rosters = self.collect_player_rosters()

        self.assign_rosters_to_players()
    

    # Helper Methods

    def __repr__(self):
        return '<{0} League>'.format(self.name.title())

    def filter_player(self, player):
        return 'games' in player and type(player['games']) != bool and self.name in player['games']

    def filter_league(self, obj):
        try:
            return obj['league'] == self.name
        except KeyError:
            return False

    def filter_intel(self, intel):
        return intel['episode'] == self.current_episode and intel['league'] == self.name

    def init_players(self):
        p_filtered = []
        for player in self.players_raw:
            p = player.copy()
            p['league'] = self
            p['house'] = player['house'][self.name]
            p['roster_id'] = player['games'][self.name]
            p_filtered.append(p)

        return [Player(**p) for p in p_filtered]

    def collect_player_rosters_ids(self):
        return map(lambda x: x.roster_id, self.players)

    def collect_player_rosters(self):
        return {roster_id: roster.values() for roster_id, roster in self.game.rosters.iteritems() if roster_id in self.roster_ids}

    def get_player(self, uid):
        return [p for p in self.players if p.id == uid][0]

    def get_house(self, hid):
        return [p.house for p in self.players if p.house.name == hid][0]

    def get_player_roster(self, uid):
        return self.get_player(uid).roster

    def get_player_house(self, uid):
        return self.get_player(uid).house.name

    def get_player_house_immunity(self, uid):
        return self.get_player(uid).house.immunity

    def get_player_episode_votes(self, player):
        predicate = lambda v: v['episode'] == str(self.current_episode) and v['player'] == player
        return next((v for v in self.votes if predicate(v)), None)

    def get_house_player(self, house):
        return [p for p in self.players if p.house.name == house][0]

    def get_roster_house(self, rid):
        return [p.house.name for p in self.players if p.roster_id == rid][0]

    def get_roster_player(self, rid):
        return [p for p in self.players if p.roster_id == rid][0]

    def get_episode_title(self, epno):
        return [e.title for id, e in self.game.episodes.iteritems() if id == str(epno)][0]

    def get_episode_number(self, epno):
        return [e.episode_number for id, e in self.game.episodes.iteritems() if id == str(epno)][0]


    def assign_rosters_to_players(self):
        """ HEALTH FOR ROSTER CHARACTER IN LEAGUE
        character_health.
            <house_id>.
                <character_id> : health
        """

        for roster_id, roster in self.rosters.iteritems():
            
            house = self.get_roster_house(roster_id)
            key = "{}{}{}".format(self.name, house, self.current_episode)
            prev_key = "{}{}{}".format(self.name, house, str(int(self.current_episode)-1))

            # GET CHAR_HEALTH FROM PREVIOUS EPISODE AND SET IT AS THE CURRENT
            if prev_key in self.game.character_health:
                
                health = self.game.character_health[prev_key].copy()
                health.update({"episode" : self.current_episode})

                self.game.character_health[key] = health
            
            # IF NO CHAR_HEALTH, GENERATE DEFAULT
            else:
                health = {
                    "episode" : self.current_episode,
                    "house" : house,
                    "roster" : roster_id,
                    "health" : dict(zip(roster, [100]*len(roster) ))
                }
                self.game.character_health[key] = health
            
            self.game.set_character_health(key, health)

            # Assign to player objects
            player = self.get_roster_player(roster_id)
            player.roster = self.rosters[player.roster_id]
            player.character_health = health['health']
            player.roster_prominence = player.get_roster_prominence(self.game.characters)
            

    # Weekly Processes

    def process_episode_results_and_publish(self):
        self.process_episode_results(missions=True)
        self.game.set_episode_as_published()

    def set_episode_as_published():
        pass

    def process_episode_results(self, votes=True, missions=False, analytics=True):
        
        print '*** >>> EPISODE {} <<< ***'.format(self.current_episode)
        if votes:
            self.score_weekly_episode()
            print '*** VOTES COUNTED ***'
            
        if missions:
        # DEVELOPER
            self.run_weekly_diplomatic_missions()     
            print '*** DIPLOMATIC MISSIONS RUN ***'
        # DEVELOPER
            self.run_weekly_assassion_missions()
            print '*** ASSASSINATION MISSIONS RUN ***'
        # DEVELOPER
            self.publish_weekly_missions_chronicle()
            print '*** MISSION ENTRIES UPDATED ***'
        
        if votes:
            self.award_weekly_points()
            self.publish_leaderboard()
            self.publish_weekly_ranking_chronicle()
            print '*** EPISODE LEADERBOARD PUBLISHED ***'

        if analytics:
            self.calculate_weekly_vote_distribution()
            print '*** ANALYTICS PUBLISHED ***'

    def score_weekly_episode(self):
        episode_votes = filter(lambda v: v['episode'] == str(self.current_episode), self.votes)
        
        for award in self.game.awards:

            score = ScoreCounter()

            for vote in episode_votes:
                for rank, points in self.game.rank_score.iteritems():
                    character = vote['vote_' + award + "_" + rank]
                    score.update({character:points})

            keys = {
                "league" : self.name,
                "episode" : self.current_episode,
                "award" :  award
            }

            self.current_episode_score[award] = score

            self.game.update_character_scores(keys, dict(score))

    def refresh_player_intelligence(self):
        for player in self.players:

            firebase_key = "{}{}{}".format(self.name, self.current_episode, player.id)

            if firebase_key in self.game.player_intelligence:
                print "CLEANING UP PLAYER INTELLIGENCE <<<"
                print firebase_key
                del self.game.player_intelligence[firebase_key]

            self.game.ref.delete('/player_intelligence/', firebase_key)
        

    def run_weekly_diplomatic_missions(self):
        
        self.refresh_player_intelligence()

        # Run diplomatic missions which have both set an agent and a target 
        for mission in filter(lambda v: v['episode'] == str(self.current_episode), self.missions):
            if mission['diplomatic_agent'] and mission['diplomatic_target_house']:
            
                player = self.get_player(mission['player'])
                
                keys = {
                    "league" : self.name,
                    "episode" : self.current_episode,
                    "player" : player.id,
                    "agent"  : mission['diplomatic_agent']
                }
                
                # if player.id == "facebook:10157044919110495":
                    # import pdb; pdb.set_trace
                
                target = self.get_house_player(mission['diplomatic_target_house'])
                target_roster = target.character_health

                intel = player.house.conduct_diplomacy(self, mission, target_roster, self.game.characters, self.players)
                intel = target.house.counter_intelligence(self, mission, intel, self.game.characters, self.players)

                intelligence = keys.copy()
                intelligence.update({"intelligence": intel})

                self.game.update_player_intelligence(keys, intelligence)


    def run_weekly_assassion_missions(self):
        episode_missions = filter(lambda v: v['episode'] == str(self.current_episode), self.missions)

        murder_set = []

        for mission in episode_missions:
            if mission['assassination_agent'] and mission['assassination_target_house'] and mission['assassination_target_character']:

                player = self.get_player(mission['player'])

                target = self.get_house_player(mission['assassination_target_house'])
                target_roster = target.character_health

                # self.game.characters, self.players
                damage_potential = player.house.plot_assassination(self, mission, target_roster)
                damage_actual = target.house.foil_assassination(self, mission, target_roster, damage_potential)  

                keys = {
                    "league" : self.name,
                    "episode" : self.current_episode,
                    "player" : player.id,
                    "house" : player.house.name,
                    "agent" : mission['assassination_agent']
                }

                murder = keys.copy()
                murder.update({"murder": damage_actual})

                murder_set.append(murder)

        # Award points for succesful assassinations
        
        if murder_set:
            
            # {'agent': u'tyrionlannister',
            #   'episode': 53,
            #   'house': u'bolton',
            #   'league': u'essos',
            #   'murder': {'bounty': 240.0,
            #              'damage_dealt': 100,
            #              'damage_intended': 100,
            #              'success': True,
            #              'target_character': u'ramsaybolton',
            #              'target_house': u'targaryen'},

            murder_print = lambda m : "House {house} assassination of {murder[target_house]}, dealt {murder[damage_dealt]} damage".format(**m)
            
            # for murder in murder_set:
            #     if murder['murder']['success']:
            #         pprint(murder_print(murder))

            # Dock Character Health 

            murder_set = self.uncover_conspiracies(murder_set)

            self.process_murder_log(murder_set)

 
        # INDEPENDENT : The faceless man the ability to take on other personas. If Jaqen kills a Character, they join this House's Roster

        # TARGARYAN : All Characters on this House's Roster gain $5\%$ Bonus on a succesful attack by a Dothraki Character


    def uncover_conspiracies(self, murder_set):
        # Points are split between the number of assailants.
        # If a stronger assassin targets the same characters

        conspiracies = defaultdict(list)
        map(lambda m: conspiracies[(m['murder']['target_house'], m['murder']['target_character'])].append(m),  murder_set)
        for pair, murders in conspiracies.iteritems():
            if len(murders) > 1:
                max_bounty = max([m['murder']['bounty'] for m in murders])
                conspirators = []
                for murder in murders:
                    if murder['murder']['bounty'] == max_bounty:
                        
                        conspirators.append(murder)
                    
                    elif murder['murder']['bounty'] < max_bounty:
                        
                        murder['murder'].update({'bounty':0,'damage_dealt':0,'success':'outwitted'})


                for conspirator in conspirators:
                    conspirator['murder'].update({'bounty': max_bounty/len(conspirators)})

        murder_set = [val for sublist in conspiracies.values() for val in sublist]
        
        return murder_set

    def process_murder_log(self, murder_set):
        """[{
        "league" : self.name,
        "episode" : self.current_episode,
        "player" : player.id,
        "house" : player.house.name,
        'agent': mission['assassination_agent'],
        "murder": {
                "target_house" : league.get_player_house(missions['player']),
                "target_character" : missions['assassination_agent'],
                "damage_intended" : damages[violence],
                "damage_dealt" : damage_dealt,
                "bounty" : 0,
                "success" : True
            }
        }]
        """
        
        self.game.update_murder_log({'league':self.name, 'episode':self.current_episode}, murder_set)
        
        succesful_murders = [murder for murder in murder_set if murder['murder']['success']]

        for murder in succesful_murders:

            mx = murder['murder']

            # Update Character Health on Player
            self.get_house_player(mx['target_house']).character_health[mx['target_character']] -= mx['damage_dealt']

            keys = murder.copy()
            keys.update({
                'house' : murder['murder']['target_house']
                })
  
            # Update Character Health on Game
            self.game.update_character_health(keys, murder['murder'])


    def refresh_chronicles(self):
        houses = [p.house.name for p in self.players]
        for house in houses:

            firebase_key = "{}{}{}".format(self.name, house, self.current_episode)

            if firebase_key in self.game.player_chronicles:
                del self.game.player_chronicles[firebase_key]

            self.game.ref.delete('/player_chronicles/', firebase_key)
        
        firebase_key = "{}{}".format(self.name, self.current_episode)
        if firebase_key in self.game.league_chronicles:
            del self.game.league_chronicles[firebase_key]

        self.game.ref.delete('/league_chronicles/', firebase_key)


    def create_public_chronicle_msg(self, cat, mission):
        d = mission['data']
        agent_house = self.get_house(d['house']).full_name
        target_house = self.get_house(d['target_house']).full_name
        target_character = self.game.characters[d['target_character']].name
        # SAD HACK
        is_silent = d['house'] == 'tyrell'
        if cat == 'failed' and not is_silent:
            code = "_".join([d['house'], d['target_house']])
            msg = "<span class=\"house\">{}</span> <span class=\"failed\">FAILED</span> an assassination attempt on <span class=\"house\">{}</span>".format(agent_house, target_house)

        elif cat == 'damage':
            health = self.get_house_player(d['target_house']).character_health[d['target_character']]
            code = "_".join([d['target_house'], d['target_character']])
            msg = "A character of <span class=\"house\">{}</span> was injured, their health is at <span class=\"health\">{}/100</span>".format(target_house, health)

        elif cat == 'death':
            code = "_".join([d['target_house'], d['target_character']])
            msg = "<span class=\"house\">{}</span>  lost <span class=\"character\">{}</span> to a succesful assassination.".format(target_house, target_character)

        else:
            code = None
            msg = None

        return code, msg

    def publish_weekly_missions_chronicle(self):

        self.refresh_chronicles()

        # import pdb ; pdb.set_trace()

        # Player
        # Update the personal Chronicle with the character damage they incurred.
        # DEVELOPER
        d_missions = self.collect_diplomatic_entries()
        a_missions = self.collect_assassination_entries()

        # DEVELOPER
        d_missions = self.set_visibility_layer(d_missions, 'diplomatic')
        # d_missions = []
        a_missions = self.set_visibility_layer(a_missions, 'assassination')
        
        for missions in [d_missions, a_missions]:
            if missions:
                for mission in missions:

                    self.get_player(mission['data']['player']).house.spread_the_word(self, mission)
            
        # Global
        # Update the public chronicle about the failures / damages / deaths
        if a_missions:
            failed_entries, damage_entries, death_entries = self.collect_league_entries(a_missions)

            for missions in [failed_entries, damage_entries, death_entries]:
                for mission in missions:
                    cat = mission['type']
                    suffix, message = self.create_public_chronicle_msg(cat, mission)

                    if not message:
                        continue

                    keys = {
                        "league" : self.name,
                        "episode" : self.current_episode,
                        "player" : mission['data']['player'],
                        "house" : mission['data']['house']
                    }

                    self.game.update_league_chronicles(keys, message, cat, suffix)


    def set_visibility_layer(self, data, mission_type):
        if data:
            logs = map(lambda d: {"type": mission_type, "success": True, "reveal": False, "data" : d}, data)
            if mission_type == 'assassination':
                for log in logs:
                    if not log['data']['success']:
                        log['success'] = False
                        log['reveal'] = True
            return logs

    def collect_diplomatic_entries(self):
        """ essos51facebook:10100288986712842
            {
              "episode" : 51,
              "intelligence" : {
                "C|NI|MARI|E|N|P" : {
                  "code" : "C|NI|MARI|E|N|P",
                  "message" : "Character has the lowest Prominence Power on the target roster",
                  "target_character" : "marei",
                  "target_house" : "nightswatch",
                  "type" : "character"
                }
              },
              "league" : "essos",
              "player" : "facebook:10100288986712842",
              "agent"  : "varys" 
            }
        """
        player_entries = [i for k, i in self.game.player_intelligence.iteritems() if self.filter_intel(i)]

        entries = []
        for entry in player_entries:
            for k, v in entry['intelligence'].iteritems():
                v['player'] = entry['player']
                if 'agent' in entry: 
                    v['agent'] = entry['agent']
                entries.append(v)

        return entries

    def collect_assassination_entries(self):
        """
        [{'episode': 51,
          'house': u'independent',
          'league': u'essos',
          'murder': {'bounty': 0,
                     'damage_dealt': 100,
                     'damage_intended': 100,
                     'success': True,
                     'target_character': u'aryastark',
                     'target_house': u'independent'},
          'player': u'facebook:10100288986712842'}]

        """
        try:
            murder_entries = self.game.murder_log[self.name + str(self.current_episode)]
        except KeyError:
            return []

        entries = []
        for entry in murder_entries:
            e = entry['murder']
            e['player'] = entry['player']
            e['house'] = entry['house']
            e['agent'] = entry['agent']
            entries.append(e)

        return entries

    def collect_league_entries(self, missions):

        get_health = lambda house, char: self.get_house_player(house).character_health[char]
        
        failed_entries = []
        damage_entries = []
        death_entries = []
        
        for mission in missions:
            
            if not mission['success'] and mission['reveal']:
                mission['type'] = 'failed'
                failed_entries.append(mission)
        
            if mission['success']:
                current_health = get_health(mission['data']['target_house'], mission['data']['target_character'])
                mission['current_health'] = current_health
            
            if mission['success'] and current_health > 0:
                mission['type'] = 'damage'
                damage_entries.append(mission)        
            
            if mission['success'] and current_health == 0:
                mission['type'] = 'death'
                death_entries.append(mission)        

        return failed_entries, damage_entries, death_entries

    def award_weekly_points(self):
        
        episode_scores = {}

        for player in self.players:

            player_roster_award_scores = {}

            for award in self.game.awards:

                award_score = self.current_episode_score[award]
                awarded_points = player.house.award_points(self, self.current_episode, award,
                    award_score, self.game.characters, player.character_health, player.missions)

                keys = {
                    "league" : self.name,
                    "episode" : self.current_episode,
                    "award" : award,
                    "player" : player.id
                }
                
                scores = {
                        'episode' : self.current_episode,
                        'player' : player.id,
                        'award' : award,
                        'scores' : dict(awarded_points)
                }

                points = sum(dict(awarded_points).values())
                
                player.house.inform_player_of_award_points(self, award, points)
                
                player_roster_award_scores[award] = points

                self.game.update_player_roster_award_scores(keys, scores)

            scores = {
                'episode' : self.current_episode,
                'league' : self.name,
                'player' : player.id,
                "scores" : player_roster_award_scores
            }

            try:

                murder_entries = self.game.murder_log[self.name + str(self.current_episode)]

                # Get awarded for murder
                murder_bounty = sum([entry['murder']['bounty'] for entry in murder_entries if entry['player'] == player.id])

            except KeyError:
                # If no murders were committed - award no points.
                murder_bounty = 0

            episode_scores[player.id] = sum(player_roster_award_scores.values()) + murder_bounty

            # DEVELOPER
            self.game.update_player_award_scores(keys, scores)

        scores = {
            'episode' : self.current_episode,
            'league' : self.name,
            "scores" : episode_scores
        }

        # DEVELOPER
        self.game.update_episode_scores(keys, scores)
        

    def publish_leaderboard(self):

        keys = {
            "league" : self.name,
            "episode" : self.current_episode,
        }

        # Select all episode score to date for current league 
        leaderboard_scores = [score['scores'] for id, score in self.game.episode_scores.iteritems() if 
            score['episode'] <= keys['episode'] and score['league'] == keys['league']]


        counter = ScoreCounter()
        map(lambda s: counter.update(s), leaderboard_scores)
       
        scores = {
            'episode' : self.current_episode,
            'league' : self.name,
            "scores" : dict(counter)
        }

        self.game.update_leaderboard(keys, scores)


    def publish_weekly_ranking_chronicle(self):

        episode_ranking = self.game.episode_scores[self.name + str(self.current_episode)]
        r = episode_ranking['scores']
        for player, points in r.iteritems():
            rank = sorted(r, key=r.get, reverse=True).index(player) + 1
            self.get_player(player).house.inform_player_of_episode_score_and_rank(self, rank, points)

        leaderboard_ranking = self.game.leaderboard[self.name + str(self.current_episode)]
        r = leaderboard_ranking['scores']
        for player, points in r.iteritems():
            rank = sorted(r, key=r.get, reverse=True).index(player) + 1
            self.get_player(player).house.inform_player_of_leaderboard_score_and_rank(self,rank,points)

    def calculate_weekly_vote_distribution(self):
        episode_votes = filter(lambda v: v['episode'] == str(self.current_episode), self.votes)
        
        houses = []
        player_points = {}
        prominence_multiplier = {}
        total_points = defaultdict(list)

        for votes in episode_votes:
            
            player = votes['player']
            house = self.get_player_house(player)
            houses.append(house)
            player_points[house] = ScoreCounter()

            for award in self.game.awards:
                for rank, points in self.game.rank_score.iteritems():
                    character = votes['vote_' + award + "_" + rank]
                    prominence_multiplier[character] = (6 - self.game.characters[character].prominence)
                    player_points[house].update({character:points})
                    total_points[character].append(points)
                    
        characters = sorted(total_points.keys())
        houses = sorted(houses)

        baseline = {char : sum(total_points[char])/ len(houses) for char in characters }
        scores = []


        for character in characters:
            
            dev_scores = []

            for house in houses:

                if character in player_points[house]:

                    multiplier = prominence_multiplier[character]
                    dev_scores.append(player_points[house][character] / baseline[character] * multiplier)
            
                else:

                    dev_scores.append(0)

            scores.append(dev_scores)


        keys = {
            "league" : self.name,
            "episode" : self.current_episode
        }

        distribution = keys.copy()
        distribution['votes'] = {
            "houses" : houses,
            "characters" : characters,
            "values" : scores
        }

        self.game.update_episode_votes(keys, distribution)