def gen_qr(account_number, account_name, info, amount):

    account_name = account_name.replace(" ", "%20")
    info = info.replace(" ", "%20")

    return f"https://api.vietqr.io/image/970422-{account_number}-gHqoyAu.jpg?accountName={account_name}&amount={amount}&addInfo={info}"

