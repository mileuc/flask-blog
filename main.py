from flask import Flask, render_template, redirect, url_for, flash, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='mp',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONFIGURE TABLES
# A one to many relationship places a foreign key on the child table referencing the parent. relationship()
# is then specified on the parent, as referencing a collection of items represented by the child

# to establish a bidirectional relationship in one-to-many, where the “reverse” side is a many to
# one, specify an additional relationship() and connect the two using the relationship.back_populates parameter:
# Child will get a parent attribute with many-to-one semantics.

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    name = db.Column(db.String(1000))

    # add parent relationship (to BlogPost)
    # This will act like a List of BlogPost objects attached to each User
    # The "author" refers to the author property in the BlogPost class
    posts = relationship("BlogPost", back_populates="author")

    # add parent relationship (to Comment)
    # This will act like a List of Comment objects attached to each User
    # "comment_author" refers to the comment_author property in the Comment class
    comments = relationship("Comment", back_populates="comment_author")


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)

    # add parent relationship (to Comment)
    # This will act like a List of Comment objects attached to each BlogPost
    # The "post" refers to the post property in the BlogPost class.
    comments = relationship("Comment", back_populates="parent_post")

    # add child relationship (to User)
    # "users.id" The users refers to the tablename of the Users class.
    # create reference to the User object, "posts" refers to the posts property in the User class
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")  # author property is now a object of the User class


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text, nullable=False)

    # add child relationship (to User)
    # "users.id" The users refers to the tablename of the Users class.
    # create reference to the User object, "comments" refers to the comments property in the User class.
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")  # comment_author property is now a object of the User class

    # add child relationship (to BlogPost)
    # "blog_posts.id" The blog_posts refers to the tablename of the BlogPost class.
    # create reference to the BlogPost object, "comments" refers to the comments property in the BlogPost class.
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")  # post property is now a object of the BlogPost class


# Create all the tables in the database
db.create_all()


# decorator is a function that wraps and replaces another function.
# since the original function is replaced, you need to remember to copy the original function’s information to the new function.
# use functools.wraps() to handle this for you.
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        #Otherwise continue with the route function
        return f(*args, **kwargs)
    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    return render_template("index.html", all_posts=posts, logged_in=current_user.is_authenticated)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Sorry, this email already exists in the database. Please log in instead.")
            return redirect(url_for("login"))

        new_user = User()
        new_user.email = form.email.data
        new_user.password = generate_password_hash(form.password.data, method="pbkdf2:sha256", salt_length=8)
        new_user.name = form.name.data
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_all_posts"))
    return render_template("register.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        login_email = form.email.data
        login_password = form.password.data
        requested_user = User.query.filter_by(email=login_email).first()
        if requested_user:
            if check_password_hash(pwhash=requested_user.password, password=login_password):
                login_user(requested_user)
                return redirect(url_for("get_all_posts"))
            else:
                flash("Sorry, wrong password! Please try again.")
                return redirect(url_for("login"))
        else:
            flash("Sorry, that email does not exist! Please try again.")
            return redirect(url_for("login"))
    return render_template("login.html", form=form, logged_in=current_user.is_authenticated)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    form = CommentForm()

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("Please login or register to comment!")
            return redirect(url_for("login"))
        new_comment = Comment()
        new_comment.body = form.comment.data
        new_comment.comment_author = current_user
        new_comment.parent_post = requested_post
        db.session.add(new_comment)
        db.session.commit()

    return render_template("post.html", post=requested_post, logged_in=current_user.is_authenticated, form=form)


@app.route("/about")
def about():
    return render_template("about.html", logged_in=current_user.is_authenticated)


@app.route("/contact")
def contact():
    return render_template("contact.html", logged_in=current_user.is_authenticated)


@app.route("/new-post", methods=["GET", "POST"])
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
    return render_template("make-post.html", form=form, logged_in=current_user.is_authenticated)


@app.route("/edit-post/<int:post_id>")
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        author=post.author,
        body=post.body
    )
    if edit_form.validate_on_submit():
        post.title = edit_form.title.data
        post.subtitle = edit_form.subtitle.data
        post.img_url = edit_form.img_url.data
        post.author = edit_form.author.data
        post.body = edit_form.body.data
        db.session.commit()
        return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, logged_in=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    # app.run(host='0.0.0.0', port=5000)
    app.run(debug=True)

