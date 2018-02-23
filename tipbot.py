import traceback
import json
import praw
import pdb
import sys
import MySQLdb
import prawcore
from decimal import *
import subprocess
import shlex
import argparse
import random
from utils import utils
import datetime
import re

class logger():

    def logline(self,tolog):
        now = datetime.datetime.now()
        with open("tipbot.log", "a") as myfile:
            myfile.write("%s: %s\n" % (str(now),tolog))


class tipbot():

    def __init__(self):
        self.utils = utils()
        self.cursor = self.utils.get_mysql_cursor()
        self.reddit = self.utils.connect_to_reddit()
        self.logger = logger()
        self.help = """You can send the following commands to the bot by PM. Do not include the [ and ], these are only to make it easier to read for you.\n\n
* signup - Will sign you up, each account can only run this once.\n
* balance - Will give you your current tips balance.\n
* deposit - Will reply with an address which you can deposit garlicoin into.\n
* withdraw [address] [amount] - Will withdraw the amount you request into the address you request.\n
* tip [amount] [user] - Tips the user with the amount you request.\n\n

To tip a user publicly use /u/garlictipsbot [amount] [user] in a reply.\n\n

If you need any further assistance please PM my creator, /u/ktechmidas"""

    def does_user_exist(self,username):
        sql = "SELECT * FROM amounts WHERE username=%s"
        self.cursor.execute(sql, (username,))
        result = self.cursor.fetchone()
        if not result:
            return 0
        else:
            return 1

    def check_address(self,address):
        #Here we check the address is correct, some users like to give us LTC addresses occasionally...
        if re.search('^G[a-zA-Z0-9]{33}$',address):
            return True
        else:
            return False

    def modify_user_balance(self,pn,username,amt):
        if amt < 0:
            self.logger.logline("%s tried to use a negative number!" % (username))
            raise Exception
        if pn == "+":
            sql = "UPDATE amounts SET amount=amount+%s WHERE username=%s"
            self.logger.logline("%s's balance has been credited by %s" % (username,amt))
        elif pn == "-":
            sql = "UPDATE amounts SET amount=amount-%s WHERE username=%s"
            self.logger.logline("%s's balance has been deducted by %s" % (username,amt))
        else:
            self.logger.logline("modify_user_balance got strange request. Aborting")
            return 1
        self.cursor.execute(sql, (amt,username,))
        return 0

    def new_withdrawal_request(self,username,address,amount):
        self.modify_user_balance("-",username,amount)
        sql = "INSERT INTO withdraw (username, address, amount, confirmed) VALUES (%s, %s, %s, 0)"
        self.cursor.execute(sql, (username,address,amount,))

    def give_user_the_tip(self,sender,receiver,addamt,bank,mention): #o.o
        if addamt >= bank+Decimal(0.01):
            try:
                self.logger.logline("%s had %s and tried to give %s. Failed due to not having enough in bank." % (sender,bank,addamt))
                self.reddit.comment(id=mention.id).reply("Sorry! You don't have enough in your account and we aren't a garlic bank! PM me with the word 'deposit' and I will send you instructions to get more delicious garlic into your account.")
                return 2
            except:
                self.logger.logline("Bot was unable to comment, perhaps rate limited?")
        else:
            self.modify_user_balance("-",sender,addamt)
            self.add_history_entry(sender,receiver,addamt,mention.id)

            if self.does_user_exist(receiver) == 1:
                self.modify_user_balance("+",receiver,addamt)
                mstr = str(receiver)+" "+str(addamt) #Probably no need for this, holdover from recode.
                try:
                    self.reddit.comment(id=mention.id).reply("Yay! You gave /u/%s garlicoin, hopefully they can now create some tasty garlic bread.\n***\n^^Wow ^^so ^^tasty ^^|| ^^Did ^^you ^^know ^^I'm ^^now ^^open ^^source? [^^click ^^here](https://github.com/ktechmidas/garlictipsbot/) ^^|| [^^Need ^^help?](https://www.reddit.com/message/compose/?to=garlictipsbot&subject=help&message=help) ^^|| [^^Dogecoin ^^partnership ^^coming ^^soon](https://np.reddit.com/r/garlicoin/comments/7u0z1w/garlictipsbot_recodeopen_sourceimportant_news/)" % (mstr))
                except:
                    self.logger.logline("Reddit doesn't seem to be responding right now...died on comment for existing user.")
                    #traceback.print_exc()
            else:
                self.create_account(receiver)
                self.modify_user_balance("+",receiver,addamt)
                try:
                    self.reddit.comment(id=mention.id).reply("Yay! You gave /u/%s %s garlicoin, hopefully they can now create some tasty garlic bread. If %s doesn't know what it is, they should read [this thread](https://np.reddit.com/r/garlicoin/comments/7smsu0/introducing_ugarlictipsbot/)\n***\n^^Wow ^^so ^^tasty ^^|| ^^Did ^^you ^^know ^^I'm ^^now ^^open ^^source? [^^click ^^here](https://github.com/ktechmidas/garlictipsbot/) ^^|| [^^Need ^^help?](https://www.reddit.com/message/compose/?to=garlictipsbot&subject=help&message=help) ^^|| [^^Dogecoin ^^partnership ^^coming ^^soon](https://np.reddit.com/r/garlicoin/comments/7u0z1w/garlictipsbot_recodeopen_sourceimportant_news/)" % (receiver, addamt, receiver))
                    self.utils.send_message(receiver,'Welcome to Garlicoin',"%s gave you some Garlicoin, we have added your new found riches to an account in your name on garlictipsbot. You can get the balance by messaging this bot with the word balance on it's own (in a new message, not as a reply to this one!) \n\nYou can also send tips to others or withdraw to your own garlicoin wallet. If there are any issues please PM /u/ktechmidas" % mention.author)
                except:
                    self.logger.logline("Reddit doesn't seem to be responding right now...died on comment & sendmsg for new user.")

    def give_user_the_tip_pm(self,sender,receiver,addamt,bank,message):
        if addamt >= bank+Decimal(0.01):
            try:
                message.reply("Sorry! You don't have enough in your account and we aren't a garlic bank! PM me with the word 'deposit' and I will send you instructions to get more delicious garlic into your account.")
                self.logger.logline("%s had %s and tried to give %s. Failed." % (sender,bank,addamt))
                return 2
            except:
                self.logger.logline("Bot was unable to comment, perhaps rate limited?")
        else:
            self.modify_user_balance("-",sender,addamt)
            self.add_history_entry(sender,receiver,addamt,mention.id)

            if self.does_user_exist(receiver) == 1:
                self.modify_user_balance("+",receiver,addamt)
                mstr = str(receiver)+" "+str(addamt) #Probably no need for this, holdover from recode.
                try:
                    message.reply("Yay! You gave /u/%s garlicoin, hopefully they can now create some tasty garlic bread." % (mstr))
                    self.utils.send_message(receiver,'Welcome to Garlicoin',"%s gave you some Garlicoin via PM" % (message.author))
                except:
                    self.logger.logline("Reddit doesn't seem to be responding right now...died on comment for existing user.")
            else:
                self.create_account(receiver)
                self.modify_user_balance("+",receiver,addamt)
                try:
                    message.reply("Yay! You gave /u/%s %s garlicoin, hopefully they can now create some tasty garlic bread. If %s doesn't know what it is, they should read [this thread](https://www.reddit.com/r/garlicoin/comments/7smsu0/introducing_ugarlictipsbot/)" % (receiver, addamt, receiver))
                    self.utils.send_message(receiver,'Welcome to Garlicoin',"%s gave you some Garlicoin, we have added your new found riches to an account in your name on garlictipsbot. You can get the balance by messaging this bot with the word balance on it's own (in a new message, not as a reply to this one!) \n\nYou can also send tips to others or withdraw to your own garlicoin wallet, send the bot the word 'help' to see how to do this. If there are any issues please PM /u/ktechmidas" % message.author)
                except:
                    self.logger.logline("Reddit doesn't seem to be responding right now...died on comment & sendmsg for new user.")

    def new_deposit(self,username): #If the user hasn't deposited with us before, he gets a flag created, else just do nothing because the flag is already there.
        sql = "SELECT * FROM deposits WHERE username=%s"
        self.cursor.execute(sql, (username,))
        if not self.cursor.rowcount:
            sql = "INSERT INTO deposits (username, confirmed, amount, txs) VALUES (%s, 0, 0, 0)"
            self.cursor.execute(sql, (username,))
    
    def get_amount_for_user(self,username):
        sql = "SELECT * FROM amounts WHERE username=%s"
        self.cursor.execute(sql, (username,))
        return Decimal(self.cursor.fetchone()[1])

    def check_mentions(self):
        unread = []
        for mention in self.reddit.inbox.mentions(limit=25):
            if mention.new == True:
                unread.append(mention)
                try:
                    self.logger.logline("Processing mention: %s by %s" % (mention.id,mention.author)) 
                    self.process_mention(mention)
                except:
                    #self.reddit.comment(id=mention.id).reply("Oops, something went wrong. Do you have an account with the bot? If not send 'signup' to me by PM. If you do have an account I may be having issues, please try again later.")
                    traceback.print_exc()
        self.reddit.inbox.mark_read(unread)
        del unread[:] #Probably not needed after the recode, since it's a local var, but still good to clean up I suppose....
    
    def create_account(self,username):
        sql = "INSERT INTO amounts VALUES (%s, 0)"
        self.cursor.execute(sql, (username,))

    def add_history_entry(self,sender,receiver,amt,mention):
        sql = "INSERT INTO history (sender, recv, amount, mention) VALUES (%s, %s, %s, %s)"
        self.cursor.execute(sql, (sender,receiver,amt,mention,))

    def get_new_address(self,username):
        return subprocess.check_output(shlex.split('/home/monotoko/garlic/garlicoin/bin/garlicoin-cli getnewaddress %s' % (username)))

    def check_redditor_exists(self,redditor):
        try:
            fullname = self.reddit.redditor(redditor).fullname
            return True
        except prawcore.exceptions.NotFound:
            self.logger.logline('{} tried to tip {} but there is no user by that name'.format(sender, receiver))
            return False

    def process_mention(self,mention):
        #print('{}\n{}\n'.format(mention.author, mention.body))
        self.logger.logline('{}\n{}\n'.format(mention.author, mention.body))
        todo = mention.body.split()
        needle = todo.index("/u/garlictipsbot") #Need to find this in multiple ways, currently tripping on u/ and capital letters.
        sender = mention.author
        addamt = todo[needle+1]
        receiver = todo[needle+2]

        #Ensure we don't have /u/ on receiver
        if receiver.count("/u/") == 1:
            receiver = receiver.replace(receiver[:3],'')

        #Make sure we're not sending our precious GRLC to nobody
        if not self.check_redditor_exists(receiver):
            self.logger.logline('%s tried to tip %s but there is no user by that name' % (sender, receiver))
            try:
                self.reddit.comment(id=mention.id).reply("You tried to tip /u/%s, but that user doesn't exist.\n***\n^^Wow ^^so ^^tasty ^^|| ^^I ^^now ^^support ^^exchange ^^from ^^and ^^to ^^other ^^cryptos [^^click ^^here](https://www.reddit.com/r/garlicoin/comments/7wehii/ugarlictipsbot_a_giveaway_important_news/) ^^|| [^^Need ^^help?](https://www.reddit.com/message/compose/?to=garlictipsbot&subject=help&message=help) ^^|| [^^Dogecoin ^^partnership ^^coming ^^soon](https://np.reddit.com/r/garlicoin/comments/7u0z1w/garlictipsbot_recodeopen_sourceimportant_news/)" % (receiver))
            except:
                self.logger.logline("Reddit doesn't seem to be responding right now...died on comment for existing user.")
            return

        addamt = Decimal(addamt)

        bank = self.get_amount_for_user(sender)

        self.give_user_the_tip(sender,receiver,addamt,bank,mention) #o.o

        #Do the calculations, giving a little leeway here.
                
    def process_command(self,message,command):
        #First we check whether the user wants to signup, if so let's process that...
        command = command.lower()
        author = message.author
        self.logger.logline("%s issued command %s" % (author,command))
        userexists = self.does_user_exist(author)
        if command != "signup" and userexists == 0:
            message.reply("Hi! This bot doesn't know who you are. Please PM the word 'signup' in a new message if you would like to start using the bot. If you think you should have a balance here please PM my carer /u/ktechmidas")
            return 2
        if command == "signup":
            if userexists == 0:
                self.create_account(author)
                message.reply("Hi! You have successfully signed up! You can check by sending the word balance in a new message to /u/garlictipsbot or send deposit to deposit some delicious garlic")
            else:
                message.reply("Hi. You already have an account so we cannot sign you up again. Please send the word balance in a new message to /u/garlictipsbot to find your balance")
        elif command == "balance":
            balance = self.get_amount_for_user(author)
            self.logger.logline("%s requested their balance. AMT: %s" % (author,balance))
            message.reply("Your balance is %s" % balance)
        elif command == "deposit":
            self.new_deposit(author)
            addy = self.get_new_address(author)
            message.reply("Hi! Our cooks have generated a deposit address just for you, it is: %s \n\n Once you have sent some garlicoin please be patient while it appears in your account.\n\n **NOTE:** You may have to wait 10-15 minutes after depositing due to the way I check deposits, this may be changing soon." % (addy))
        elif command == "help":
            message.reply(self.help)
        else:
            message.reply("Sorry! I did not understand the command you gave. Please write a new PM (not reply) with help and I will reply with what I accept.")

    def process_multi_command(self,message,command):
        author = message.author
        userexists = self.does_user_exist(author)
        if userexists == 0:
            self.logger.logline("%s tried to issue command %s while not signed up" % (author,command))
            message.reply("Hi! This bot doesn't know who you are. Please PM the word 'signup' in a new message if you would like to start using the bot. If you think you should have a balance here please PM my carer /u/ktechmidas")
        msgsplit = message.body.split()
        msgsplit[0] = msgsplit[0].lower()
        self.logger.logline("%s issued command %s" % (author,message.body))
        if msgsplit[0] == "withdraw":
            try:
                address = msgsplit[1]
                #if address.len() != 34:
                    #raise Exception
                amt = Decimal(msgsplit[2])
            except:
                message.reply("You don't seem to have sent me an amount or address, please resend in the format withdraw address amount - PM /u/ktechmidas for help if you need it.")
                self.logger.logline("%s sent invalid amount" % (author))
                return 1
            try:
                if not self.check_address(address):
                    raise Exception #Objection!
                amtleft = self.get_amount_for_user(author)
                ##amtleft = Decimal(self.cursor.fetchone()[1])
                
                if amt <= amtleft:
                    self.new_withdrawal_request(author,address,amt)
                    message.reply("Hi, your withdrawal request has been accepted! Please note this is a manual process for now. PM my carer /u/ktechmidas if you need it urgently.")
                    self.logger.logline("%s has a new withdrawal waiting. AMT: %s" % (author,amt))
                    return 0
                else:
                    self.logger.logline("%s tried to withdraw more than was in their account, AMT: %s" % (author,amt))
                    message.reply("Oops, you tried to withdraw more than is in your account. Please send a message with the word 'balance' to get your current balance")
                    return 1
            except:
                message.reply("It appears you tried to send a withdrawal request, but we couldn't figure out the format. Please resend it as 'withdraw address amount' - It's also possible you gave an invalid Garlicoin address, please check it.")
                traceback.print_exc()
        elif msgsplit[0] == "tip":
            #The user wants to tip another privately, that's cool, we can do that too.
            try:
                addamt = Decimal(msgsplit[1])
                receiver = msgsplit[2]
            except:
                message.reply("Hi, the bot did not understand your request. Please send tips in the format 'tip amount user' as a new message, without the quotes.")
                return 1

            #Ensure our decimal is *not* a negative number.
            if addamt < 0:
                message.reply("You tried to use a negative number, you'll make people sad if you steal their precious garlic...")
                self.logger.logline("%s tried to use a negative number!" % (author))
                return 1

            #Make sure we're not sending our precious GRLC to nobody
            if not self.check_redditor_exists(receiver):
                self.logger.logline('%s tried to tip %s but there is no user by that name' % (author, receiver))
                message.reply('You tried to tip /u/%s, but there is no user by that name.' % (receiver))
                return 1

            bank = self.get_amount_for_user(author)
            self.give_user_the_tip_pm(self,sender,receiver,addamt,bank,mention) #o.o


    def check_messages(self):
        #Alright, here's where things get a little fun/messy. 
        unread = []
        for indmessage in self.reddit.inbox.messages(limit=5):
            if indmessage.new == True:
                unread.append(indmessage)
                try:
                    command = indmessage.body
                    if not ' ' in command:
                        #If there's only one word it's an information command, eg deposit/balance/help
                        self.process_command(indmessage,command)
                    else:
                        self.process_multi_command(indmessage,command)
                except Exception as ex:
                    print("Something went wrong processing commands...skipping this one")
                    #print(ex)
                    traceback.print_exc()
        self.reddit.inbox.mark_read(unread)



    def main(self):

        try:
            me = self.reddit.user.me()
        except:
            print("Something went wrong. Please check Reddit for details")
            sys.exit()

        if me != "garlictipsbot":
            print("Not the correct user. Aborting!")

        #First we check any mentions in comments so we can do the tipping, then check the private messages of the bot.
        self.check_mentions()
        self.check_messages()
        print("Done, next round in 15")


tipobj = tipbot()
tipobj.main()
