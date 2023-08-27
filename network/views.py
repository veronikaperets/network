from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from .models import User, Post
from django.utils import timezone
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import json




def index(request):
    posts_list = Post.objects.all().order_by('-timestamp')
    paginator = Paginator(posts_list, 10)  # Show 10 posts per page

    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        posts = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        posts = paginator.page(paginator.num_pages)

    return render(request, 'network/index.html', {'posts': posts})




def login_view(request):
    if request.method == "POST":

        # Attempt to sign user in
        username = request.POST["username"]
        password = request.POST["password"]
        user = authenticate(request, username=username, password=password)

        # Check if authentication successful
        if user is not None:
            login(request, user)
            return HttpResponseRedirect(reverse("index"))
        else:
            return render(request, "network/login.html", {
                "message": "Invalid username and/or password."
            })
    else:
        return render(request, "network/login.html")


def logout_view(request):
    logout(request)
    return HttpResponseRedirect(reverse("index"))


def register(request):
    if request.method == "POST":
        username = request.POST["username"]
        email = request.POST["email"]

        # Ensure password matches confirmation
        password = request.POST["password"]
        confirmation = request.POST["confirmation"]
        if password != confirmation:
            return render(request, "network/register.html", {
                "message": "Passwords must match."
            })

        # Attempt to create new user
        try:
            user = User.objects.create_user(username, email, password)
            user.save()
        except IntegrityError:
            return render(request, "network/register.html", {
                "message": "Username already taken."
            })
        login(request, user)
        return HttpResponseRedirect(reverse("index"))
    else:
        return render(request, "network/register.html")
    
def new_post(request):
    if request.method == "POST":
        # Check if the request has a JSON content type, which would indicate it's an AJAX request
        if request.headers.get('content-type') == 'application/json':
            data = json.loads(request.body)
            content = data.get("content")
        else:
            content = request.POST.get("content")
        
        post = Post(user=request.user, content=content, timestamp=timezone.now())
        post.save()
        
        # Respond appropriately based on the request type
        if request.headers.get('content-type') == 'application/json':
            return JsonResponse({"status": "success"})
        else:
            return HttpResponseRedirect(reverse("index"))

    return render(request, "network/new_post.html")


def profile(request, username):
    user = User.objects.get(username=username)
    posts = Post.objects.filter(user=user).order_by('-timestamp')
    
    current_user = request.user
    is_following = current_user.following.filter(id=user.id).exists() if current_user.is_authenticated else False

    context = {
        'profile_user': user,
        'posts': posts,
        'is_following': is_following
    }

    return render(request, "network/profile.html", context)


def toggle_follow(request, username):
    user_to_follow = User.objects.get(username=username)
    current_user = request.user
    
    if current_user.is_authenticated and current_user != user_to_follow:
        if current_user.following.filter(id=user_to_follow.id).exists():
            current_user.following.remove(user_to_follow)
            action = "unfollow"
        else:
            current_user.following.add(user_to_follow)
            action = "follow"
        return JsonResponse({"action": action}, status=200)
    else:
        return JsonResponse({"error": "Invalid action."}, status=400)
    
def following(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("login"))
    
    # Fetch posts made by users that the current user follows
    followed_users = request.user.following.all()
    posts_list = Post.objects.filter(user__in=followed_users).order_by('-timestamp')

    paginator = Paginator(posts_list, 10)  # Show 10 posts per page

    page = request.GET.get('page')
    try:
        posts = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page.
        posts = paginator.page(1)
    except EmptyPage:
        # If page is out of range (e.g. 9999), deliver last page of results.
        posts = paginator.page(paginator.num_pages)

    return render(request, "network/following.html", {"posts": posts})

def edit_post(request, post_id):
    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({"error": "Post not found."}, status=404)

    if request.user != post.user:
        return JsonResponse({"error": "You are not authorized to edit this post."}, status=403)
    
    if request.method == 'PUT':
        data = json.loads(request.body)
        post.content = data.get("content", "")
        post.save()
        return JsonResponse({"status": "success"}, status=200)


def like_post(request, post_id):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Not authenticated."}, status=401)

    try:
        post = Post.objects.get(id=post_id)
    except Post.DoesNotExist:
        return JsonResponse({"error": "Post not found."}, status=404)

    if request.method == "PUT":
        data = json.loads(request.body)
        action = data.get("action")
        
        already_liked = post in request.user.liked_posts.all()

        if action == "like" and not already_liked:
            # Add the post to user's liked posts and increment post's likes count
            request.user.liked_posts.add(post)
            post.likes += 1
            post.save()

        elif action == "unlike" and already_liked:
            # Remove the post from user's liked posts and decrement post's likes count
            request.user.liked_posts.remove(post)
            post.likes -= 1
            post.save()
            
        else:
            # Invalid action or action that's already been taken
            return JsonResponse({"error": "Invalid action or action already taken."}, status=400)

        # Return the updated likes count
        return JsonResponse({"status": "success", "likes": post.likes})

    return JsonResponse({"error": "Invalid method."}, status=405)



