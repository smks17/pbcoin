DEFAULT_SUBSIDY = 50

class Trx:
    sender: str
    recipient: str
    amount: float
    def __init__(self, *args):
        if len(args) == 0:
            # this is subsidy trx
            #TODO
            self.sender = ""
            self.recipient = "self"
            self.amount = DEFAULT_SUBSIDY
        elif len(args) == 3:
            self.sender = args[0]
            self.recipient = args[1]
            self.amount = args[3]
        else:
            assert (False, "bad args")