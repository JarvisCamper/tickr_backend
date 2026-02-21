from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APITestCase

from user.models import User
from user.serializers import LoginSerializer, SignupSerializer


class LoginSerializerTests(APITestCase):
	def test_login_serializer_valid_with_email(self):
		user = User.objects.create_user(
			email="admin@admin.com",
			password="admin",
			username="admin",
		)

		serializer = LoginSerializer(data={"email": "admin@admin.com", "password": "admin"})
		self.assertTrue(serializer.is_valid(), serializer.errors)
		self.assertEqual(serializer.validated_data["user"].pk, user.pk)

	def test_login_serializer_invalid_password(self):
		User.objects.create_user(email="admin@admin.com", password="admin")
		serializer = LoginSerializer(data={"email": "admin@admin.com", "password": "wrong"})
		with self.assertRaises(AuthenticationFailed):
			serializer.is_valid(raise_exception=True)


class LoginEndpointTests(APITestCase):
	def test_login_member_redirects_to_timer(self):
		User.objects.create_user(email="m@x.com", password="pass", username="m")

		url = reverse("login")
		resp = self.client.post(url, {"email": "m@x.com", "password": "pass"}, format="json")

		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("role"), "member")
		self.assertEqual(resp.data.get("redirect_url"), "/timer")
		self.assertIn("access", resp.data)
		self.assertIn("refresh", resp.data)
		self.assertIn("user", resp.data)

	def test_login_admin_redirects_to_admin(self):
		User.objects.create_superuser(email="admin@admin.com", password="admin")

		url = reverse("login")
		resp = self.client.post(url, {"email": "admin@admin.com", "password": "admin"}, format="json")

		self.assertEqual(resp.status_code, status.HTTP_200_OK)
		self.assertEqual(resp.data.get("role"), "admin")
		self.assertEqual(resp.data.get("redirect_url"), "/admin")
		self.assertTrue(resp.data.get("is_admin"))

	def test_login_user_not_found(self):
		url = reverse("login")
		resp = self.client.post(url, {"email": "missing@x.com", "password": "x"}, format="json")

		self.assertIn(resp.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})
		self.assertIn("detail", resp.data)


class SignupSerializerTests(APITestCase):
	def test_signup_serializer_accepts_password2(self):
		serializer = SignupSerializer(
			data={
				"email": "p2@example.com",
				"username": "p2",
				"password": "secret123",
				"password2": "secret123",
			}
		)
		self.assertTrue(serializer.is_valid(), serializer.errors)

	def test_signup_serializer_accepts_confirm_password_alias(self):
		serializer = SignupSerializer(
			data={
				"email": "cp@example.com",
				"username": "cp",
				"password": "secret123",
				"confirmPassword": "secret123",
			}
		)
		self.assertTrue(serializer.is_valid(), serializer.errors)
