I want to write a Discord bot that will be added to a discord channel for keeping track of snooker score for snooker session.

We have 4 fixed people, in which each session of snooker has 2 to 4 players joining, playing some number of sets which is different for each session.

the bot will act as the digital scoreboard for our game, which should have the score calculation as follow:
for 2 players, use the normal snooker game rules
for 3-4 players, each player will play individually in order, with the peanlty points shared among the remaining players in case a foul is commited, rounding up to the nearest integers

the order should be shuffled for each set when playing with 3-4 players, which shouldn't repeat if possible
for example, for 3 players, the order should be first use up ABC, CBA, ACB for the first 3 sets, then the order can repeat if more sets are played.

the bot will be activated with discord command written by any of the members in the channel, then a session with the current date should be opened.

then subsequently, user should be able to interact with the bot with buttons

first allow user to select the number of players in this session

then a set should be started, showing each balls for each player, and increment the score accordingly when a button is pressed

peanlty should also be implemented, so that user can select which player commited a foul, and on which ball. points should be added to the remaining players according to rules above.

also show buttons to allow user to start a new set (and saving the current set), or to end the session once all sets have been played

the time, score for each session should be persisted