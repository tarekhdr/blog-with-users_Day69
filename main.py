from flask import Flask, render_template, redirect, request, url_for, flash
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps
from flask import abort

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

# CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)


# create admin_only decorator
def admin_only(function):
    @wraps(function)
    def decorated_function(*args, **kwargs):
        # if id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # otherwise continue with the route function / authorized admin
        else:
            return function(*args, **kwargs)
    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# CONFIGURE TABLES
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(100), nullable=False)
    name = Column(String(1000), nullable=False)

    # this will act like a list of BlogPost objects attached to each other
    # the author refers to the author property in the BlogPost class
    posts = relationship("BlogPost", back_populates='author')
    comments = relationship("Comment", back_populates='commenter')

    def __init__(self, email, password, name):
        self.email = email
        self.name = name
        self.password = password


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = Column(Integer, primary_key=True)

    # create foreign key, "users.id" the users refers to the tablename of user
    author_id = db.Column(Integer, ForeignKey('users.id'))

    # create reference to the user object, the 'posts' refers to the posts' property in the User class
    author = relationship("User", back_populates="posts")

    # create reference to the comment object, the '...' refers to the ... property in the Comment class
    comments = relationship("Comment", back_populates="blog_comment")

    title = Column(String(250), unique=True, nullable=False)
    subtitle = Column(String(250), nullable=False)
    date = Column(String(250), nullable=False)
    body = Column(Text, nullable=False)
    img_url = Column(String(250), nullable=False)


class Comment(db.Model):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True, autoincrement=True)
    text = Column(Text, nullable=False)

    # create foreign key, "users.id" the users refers to the tablename of User
    commenter_id = db.Column(Integer, ForeignKey('users.id'))
    # create reference to the user object, the 'comments' refers to the comments' property in the user class
    commenter = relationship("User", back_populates="comments")

    # create foreign key, "blog_posts.id" the blog_posts refers to the tablename of BlogPost
    blog_post_id = db.Column(Integer, ForeignKey('blog_posts.id'))
    # create reference to the BlogPost object, the '...' refers to the .... property in the BlogPost class
    blog_comment = relationship("BlogPost", back_populates="comments")

    def __init__(self, text, blog_post_id, commenter_id):
        self.text = text
        self.blog_post_id = blog_post_id
        self.commenter_id = commenter_id


# db.create_all()

users = {}
all_users = db.session.query(User).with_entities(User.email).all()
for user in all_users:
    users[user.email] = {'password': 'Secret'}


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, current_user=current_user)


@app.route('/register', methods=["POST", "GET"])
def register():
    form = RegisterForm()

    if request.method == "POST" and form.validate_on_submit():
        if request.form.get("email") in users:
            flash("You've already signed up with that email, log in instead!")
            form = LoginForm()
            return redirect(url_for('login', form=form))

        hash_and_salted_password = generate_password_hash(
            password=request.form.get("password"),
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=request.form.get("email"),
            password=hash_and_salted_password,
            name=request.form.get("name")
        )
        db.session.add(new_user)
        db.session.commit()

        # login and authenticate user after adding details to database
        login_user(new_user)

        return redirect(url_for('get_all_posts', current_user=current_user))

    return render_template("register.html", form=form)


@app.route('/login', methods=["POST", "GET"])
def login():
    form = LoginForm()
    if request.method == "POST" and form.validate_on_submit():
        email = request.form["email"]
        password = request.form["password"]
        # email does not exist in user database table
        if email not in users:
            flash("The username/email does not exist!")
            return redirect(url_for('login', form=form))
        else:
            # find user by email entered
            new_user = User.query.filter_by(email=email).first()
            # check stored password hash against entered password hashed
            if new_user and check_password_hash(pwhash=new_user.password, password=password):
                # login and authenticate user after adding details to database
                login_user(new_user)
                print(current_user.id)
                return redirect(url_for('get_all_posts', current_user=current_user))
            else:
                flash("The password is incorrect, Please try again")
                return redirect(url_for('login', form=form))
    else:
        return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts', current_user=current_user))


@app.route("/post/<int:post_id>", methods=["POST", "GET"])
def show_post(post_id):
    form = CommentForm()
    requested_post = BlogPost.query.get(post_id)

    all_comments = db.session.query(Comment).filter_by(blog_post_id=post_id).all()

    gravatar = Gravatar(app,
                        size=100,
                        rating='g',
                        default='retro',
                        force_default=False,
                        force_lower=False,
                        use_ssl=False,
                        base_url=None)

    if request.method == "POST":
        if form.validate_on_submit() and current_user.is_authenticated:
            comment_text = form.comment.data
            commenter_id = current_user.id
            blog_post_id = post_id
            new_comment = Comment(
                text=comment_text,
                blog_post_id=blog_post_id,
                commenter_id=commenter_id
            )
            db.session.add(new_comment)
            db.session.commit()
        else:
            flash("You need to login or register to comment")
            return redirect(url_for('login'))

    return render_template("post.html", post=requested_post, comments=all_comments, gravatar=gravatar, form=form, current_user=current_user)


@app.route("/about")
def about():
    return render_template("about.html", current_user=current_user)


@app.route("/contact")
def contact():
    return render_template("contact.html", current_user=current_user)


@app.route("/new-post", methods=["POST", "GET"])
@admin_only
def add_new_post():
    form = CreatePostForm()

    if form.validate_on_submit():
        new_post = BlogPost(
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            author=current_user,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))

    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@admin_only
@login_required
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        # author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        # post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(debug=True)
    # app.run(host='0.0.0.0', port=5000)
