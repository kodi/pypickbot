from ircbotdomain.domain import IrcBotDomain

def setup(app):
    app.add_domain(IrcBotDomain)

