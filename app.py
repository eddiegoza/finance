import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from string import digits, ascii_letters, punctuation
from helpers import apology, login_required, lookup, usd
import string
import datetime

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    userid = session["user_id"]

    #Query for transactions to display
    transactions_db = db.execute(
        "SELECT symbol, name, price, SUM(shares) as totalshares FROM transactions where userID=? GROUP BY symbol",
         userid)

    # Query for cash
    cash = db.execute("SELECT cash FROM users WHERE id=?", userid)[0]["cash"]
    grand_total = cash
    for transaction in transactions_db:
        grand_total += transaction["price"] * transaction["totalshares"]
    return render_template("index.html", transactions=transactions_db, cash=cash, usd=usd, grand_total=grand_total)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # check if fields have been filled
        if not symbol:
            return apology("Please fill in the symbol field")
        if not shares:
            return apology("Please fill in the shares field")

        if shares < 0:
            return apology("Shares cannot be negative")

        # check if symbol input matches the with symbols in the database
        symbol_stock = lookup(symbol.upper())
        if not symbol_stock:
            return apology("Please input valid symbol for the stock you wish to buy")

        # remember user logged in
        userid = session["user_id"]
        usernames = db.execute("SELECT username FROM users WHERE id=?", userid)
        username = usernames[0]["username"]

        # latest price of the stock

        real_price = symbol_stock["price"]
        stock_name = symbol_stock["name"]

        # check whether the user has enough balance to buy stock
        balances = db.execute("SELECT cash FROM users WHERE id=?", userid)
        balance = balances[0]["cash"]

        # calculate cost of stock bought
        cost = real_price * shares

        #set variable for time
        date = datetime.datetime.now()

        # check if user has enough cash to complete the buy
        if cost > balance:
            return apology("Sorry, you do not have enough balance to make the purchase")

        else:
            balance -= cost

            # update the cash colomn in the users table
            db.execute("UPDATE users SET cash=? WHERE id=?", balance, userid)

            # create a new table to track the transactions and update it as well
            db.execute("INSERT INTO transactions (symbol, price, shares, name, userID, cost_price, time) VALUES (?, ?, ?, ?, ?, ?,?)",
             symbol, real_price,shares, stock_name, userid, cost, date)

        # confirmation message display
        flash("transaction succesful")

        # return to the home page
        return redirect("/")
    else:
        userid = session["user_id"]
        symbols = db.execute("SELECT symbol FROM transactions WHERE userID=? GROUP BY symbol", userid)
        return render_template("buy.html", symbols=symbols)


@app.route("/history")
@login_required
def history():

    #remember user in session
    userid = session["user_id"]
    transactions = db.execute("SELECT * FROM transactions WHERE userID=?", userid)
    return render_template("history.html", transactions=transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        # get input from user
        symbol = request.form.get("symbol")

        # check validity of input
        if not symbol:
            return apology("symbol required", 400)

        # get information about the share
        stock = lookup(symbol.upper())

        # check if symbol exists in the look-up
        if stock == None:
            return apology("Invalid symbol")
        else:
            return render_template("quoted.html", name=stock["name"], price=stock["price"], Symbol=stock["symbol"])

    else:
        return render_template("qoute.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # add new user credentials into the database
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # check validity of new credentials

        if not username:
            return apology("Invalid username and/or password", 400)
        if not password:
            return apology("Invalid username and/or password", 400)
        if not confirmation:
            return apology("passwords did not match", 405)

        #check if the password meets requirements
        numberscount = 0
        letterscount = 0
        symbolscount = 0

        # count all the necessary  in the password
        for element in password:
            if element in digits:
                numberscount += 1
            if element in ascii_letters:
                letterscount += 1
            if element in punctuation:
                symbolscount += 1
        # check if password has all the characters needed to make a password
        if numberscount < 1:
            return apology("please include a number in your password")
        if letterscount < 1:
            return apology("please include a letter in your password")
        if symbolscount < 1:
            return apology("please include a special symbol in your password(.&*@)")
        # set lenth for password
        if len(password) < 6:
            return apology("password should be atleast 6 characters")
        # check if the second password matches with the first password
        if not confirmation:
            return apology("Please re-type the password", 400)

        if password != confirmation:
            return apology("passwords did not match")

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # check if user does not exist alrady
        if len(rows) != 0:
            return apology("Usename is already in use. Please choose another")

        # hash password and save both username ans password to the database
        hashed = generate_password_hash(request.form.get("password"))

        # if no more errors, enter the registrant into the database
        db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hashed)

        # Log-in the user and remember which user has logged in
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))
        session["user_id"] = rows[0]["id"]

        # redirect user to home page
        return redirect("/")

    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares = int(request.form.get("shares"))

        # render apology if user fais to select stock or does not own selected shares
        if not symbol:
            return apology("Please enter symbol")

        if not shares:
            return apology("Please enter shares")

        if shares <= 0:
            return apology("Shares cannot be less than 1")

        # check if symbol input matches the with symbols in the database
        symbol_stock = lookup(symbol.upper())
        if not symbol_stock:
            return apology("Please input valid symbol for the stock you wish to buy")

        # remeber user logged in
        userid = session["user_id"]

        # Query for  shares in the database
        cash_db = db.execute("SELECT cash FROM users WHERE id=?", userid)
        user_cash = cash_db[0]["cash"]

        # latest price of the stock
        real_price = symbol_stock["price"]
        stock_name = symbol_stock["name"]

        # Query for user shares
        shares_db = db.execute("SELECT shares FROM transactions WHERE userID=? and symbol=? GROUP BY symbol",
        userid, symbol)[0]["shares"]
        if shares > shares_db:
            return apology("You cannot make this transaction")
        else:
            # calculate cost of stock bought
            sale = real_price * shares

            # check whether the user has enough balance to buy stock
            balances = db.execute("SELECT cash FROM users WHERE id=?", userid)
            balance = balances[0]["cash"]

            # update user balance
            balance += sale

            # update the cash colomn in the users table
            db.execute("UPDATE users SET cash=? WHERE id=?", balance, userid)

            # set variable for time
            date = datetime.datetime.now()

            # create a new table to track the transactions and update it as well
            db.execute("INSERT INTO transactions (symbol, price, shares, name, userID, selling_price, time) VALUES (?, ?, ?, ?, ?, ?,?)",
             symbol, real_price, -shares, stock_name, userid, sale, date)

            # confirmation message display
            flash("transaction succesful")

            return redirect("/")
    else:
        userid = session["user_id"]
        symbols = db.execute("SELECT symbol FROM transactions WHERE userID=? GROUP BY symbol", userid)
        return render_template("sell.html", symbols=symbols)
