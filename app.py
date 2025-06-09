import os

from rapidfuzz import fuzz

from flask import Flask, flash, redirect, render_template, request, session, send_file
from flask_session import Session

from cs50 import SQL

from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

db = SQL("sqlite:///main.db")

upload_folder = "uploads/"


@app.route("/")
def index():
    search = request.args.get("search")

    no_of_files_in_a_page = 5

    if search == "":
        flash("Enter something in search")
        return render_template("index.html")

    if not search:
        return render_template("index.html")

    search = search.lower()

    file_names = db.execute("SELECT original_name, disk_name_id FROM filesinfo")
    matches = []

    for i in file_names:
        score = fuzz.partial_ratio(search, i["original_name"].lower())
        if score > 45:
            matches.append((score, i["original_name"], i["disk_name_id"]))

    matches.sort(reverse=True)

    no_of_pages = len(matches) // no_of_files_in_a_page

    if len(matches) == 0:
        no_of_pages = 1

    if len(matches) % no_of_files_in_a_page != 0:
        no_of_pages += 1

    page_no = request.args.get("page", 1)

    try:
        page_no = int(page_no)
    except:
        flash("Page number must be an integer")
        return render_template("index.html", file_names = matches[: no_of_files_in_a_page],
                               no_of_pages = no_of_pages, page_no = 1, search = search)

    page_no = page_no

    if page_no > no_of_pages or page_no < 1 :
        flash("Requested page number is out of bounds")
        return render_template("index.html", file_names = matches[: no_of_files_in_a_page],
                               no_of_pages = no_of_pages, page_no = 1, search = search)

    temp = (page_no - 1) * no_of_files_in_a_page
    return render_template("index.html", file_names = matches[temp : temp + no_of_files_in_a_page],
                           no_of_pages = no_of_pages, page_no = page_no, search = search)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    username = request.form.get("username")
    password = request.form.get("password")
    confirmpassword = request.form.get("confirmation")

    if not username:
        flash("Username should not be empty")
        return redirect('/signup')

    elif not password:
        flash("Password should not be empty")
        return redirect('/signup')

    elif not confirmpassword:
        flash("Confirm Password should not be empty")
        return redirect('/signup')

    elif db.execute("SELECT * FROM users WHERE username = ?", username):
        flash("Username already exists")
        return redirect('/signup')

    elif password != confirmpassword:
        flash("Passwords do not match")
        return redirect('/signup')

    session["user_id"] = db.execute("insert into users(username, password) values(?, ?)", username,
            generate_password_hash(password))

    flash("Signed Up!")
    return redirect("/")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username")
    password = request.form.get("password")

    if not username:
        flash("Username should not be empty")
        return redirect('/login')

    elif not password:
        flash("Password should not be empty")
        return redirect('/login')

    row = db.execute(
        "SELECT * FROM users WHERE username = ?", username
    )

    if len(row) != 1 or not check_password_hash(row[0]["password"], password):
        flash("Username or Password is incorrect")
        return redirect('/login')

    session["user_id"] = row[0]["id"]

    flash("Logged in!")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()

    flash("Logged out!")
    return redirect("/")


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if session.get("user_id") is None:
        flash("Log In/Sign Up to upload files")
        return redirect("/login")

    if request.method == "GET":
        return render_template("upload.html")

    file = request.files.get("file")
    desc = request.form.get("description")

    if not file or file.filename == '':
        flash("You have not selected any file to upload")
        return redirect("/upload")

    if not file.mimetype == 'application/pdf':
        flash("Select only PDF files to upload")
        return redirect("/upload")

    file.stream.seek(0, 2)
    size = round(file.stream.tell() / (1024 * 1024), 4)
    file.stream.seek(0)

    if size > 500:
        flash("File size exceeds the size limit")
        return redirect("/upload")

    if not desc:
        disk_name_id = db.execute("INSERT INTO filesinfo(uploader_id, original_name, size) VALUES(?, ?, ?)",
                                  session["user_id"], file.filename, size)
    else:
        disk_name_id = db.execute("INSERT INTO filesinfo(uploader_id, original_name, description, size) VALUES(?, ?, ?, ?)",
                                  session["user_id"], file.filename, desc, size)

    disk_name = os.path.join(upload_folder, str(disk_name_id) + ".pdf")
    file.save(disk_name)

    flash("File has been uploaded!")
    return redirect("/")



@app.route("/profile")
def profile():
    if session.get("user_id") is None:
        flash("Log In to access your profile")
        return redirect("/login")

    files = db.execute("SELECT original_name, upload_time, disk_name_id from filesinfo where uploader_id = ?",
                       session["user_id"])
    username = db.execute("SELECT username from users where id = ?", session["user_id"])[0]["username"]

    return render_template("profile.html", files = files, username = username)


@app.route("/uploader_file_view")
def uploader_file_view():
    file_id = request.args.get("file_id")

    try:
        file_id = int(file_id)
    except:
        flash("invalid file")
        return redirect("/profile")

    if session.get("user_id") is None:
        flash("Log In to access your files")
        return redirect("/login")

    file_detail = db.execute("SELECT original_name, size, description, upload_time from filesinfo WHERE uploader_id = ? and disk_name_id = ?",
                             session["user_id"], file_id)

    if not file_detail:
        flash("You have not uploaded this file")
        return redirect("/")

    file_detail = file_detail[0]

    return render_template("uploader_view.html", file_name = file_detail["original_name"],
                           size = file_detail["size"], desc = file_detail["description"],
                           ut = file_detail["upload_time"], file_id = file_id)

@app.route('/delete/<file_id>')
def delete(file_id):
    if session.get("user_id") is None:
        flash("Log In to delete your files")
        return redirect("/login")

    file_detail = db.execute("SELECT original_name, size, description, upload_time from filesinfo WHERE uploader_id = ? and disk_name_id = ?",
                             session["user_id"], file_id)

    if not file_detail:
        flash("You have not uploaded this file")
        return redirect("/")

    filepath = os.path.join(upload_folder, str(file_id) + ".pdf")
    os.remove(filepath)

    db.execute("DELETE FROM filesinfo WHERE disk_name_id = ?", file_id)

    flash("File deleted")
    return redirect("/profile")


@app.route("/downloader_file_view")
def downloader_file_view():
    file_id = request.args.get("file_id")

    try:
        file_id = int(file_id)
    except:
        flash("invalid file")
        return redirect("/")

    file_detail = db.execute("SELECT original_name, uploader_id, size, description, upload_time from filesinfo where disk_name_id = ?",
                             file_id)

    if not file_detail:
        flash("Invalid file")
        return redirect("/")

    file_detail = file_detail[0]

    uploader_username = db.execute("SELECT username from users where id = ?",
                                   file_detail["uploader_id"])[0]["username"]

    return render_template("downloader_view.html",u_username = uploader_username, file_name = file_detail["original_name"],
                           size = file_detail["size"], desc = file_detail["description"],
                           ut = file_detail["upload_time"], file_id = file_id)


@app.route('/download/<file_id>/<original_name>')
def download(file_id, original_name):
    path = os.path.join(upload_folder, str(file_id) + ".pdf")

    if not os.path.isfile(path):
        flash("Invalid file")
        return redirect("/")

    return send_file(path, as_attachment=True, download_name=original_name)


@app.route("/change_pass", methods=["GET", "POST"])
def change_password():
    if session.get("user_id") is None:
        flash("Log In to change your account password")
        return redirect("/login")

    if request.method == "GET":
        return render_template("change_pass.html")

    if not request.form.get("password"):
        flash("must provide new password")
        return redirect("/change_pass")

    elif not request.form.get("confirmation"):
        flash("must confirm new password")
        return redirect("/change_pass")

    elif request.form.get("password") != request.form.get("confirmation"):
        flash("passwords do not match")
        return redirect("/change_pass")

    db.execute("update users set password=? where id=?", generate_password_hash(
        request.form.get("password")), session["user_id"])

    flash("Password Changed!")
    return redirect("/profile")

@app.route("/delete_acc", methods=["GET", "POST"])
def delete_acc():
    if session.get("user_id") is None:
        flash("Log In to delete your account")
        return redirect("/login")

    if request.method == "GET":
        return render_template("delete_acc.html")

    password = request.form.get("password")
    confirm = request.form.get("confirm")

    if not password:
        flash("Enter password of your account")
        return redirect("/delete_acc")
    elif not confirm:
        flash("Enter 'CONFIRM'")
        return redirect("/delete_acc")

    row = db.execute("SELECT password from users where id=?", session["user_id"])

    if not check_password_hash(row[0]["password"], password):
        flash("password is incorrect")
        return redirect("/delete_acc")
    elif confirm != "CONFIRM":
        flash("Enter 'CONFIRM' properly")
        return redirect("/delete_acc")

    file_ids = db.execute("SELECT disk_name_id as id from filesinfo where uploader_id=?", session["user_id"])

    for i in file_ids:
        filepath = os.path.join(upload_folder, str(i["id"]) + ".pdf")
        os.remove(filepath)
        db.execute("DELETE FROM filesinfo WHERE disk_name_id = ?", i["id"])

    db.execute("DELETE FROM users WHERE id=?", session["user_id"])

    session.clear()
    flash("account deleted")
    return redirect("/")

