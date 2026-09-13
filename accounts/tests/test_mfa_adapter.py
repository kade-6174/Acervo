"""MFA AdapterおよびMultiFernet暗号化に関するテスト。"""

from allauth.mfa.adapter import get_adapter
from allauth.mfa.models import Authenticator
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import TOTP, format_hotp_value, hotp_value
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import SuspiciousOperation
from django.test import TestCase

from accounts.adapters import AcervoMFAAdapter
from accounts.models import User


class AcervoMFAAdapterTests(TestCase):
    KEY_PRIMARY = "0YFsuKhANUHwqSsmdjDwiT5GUQXzE7d1c5bUpFPJgy4="
    KEY_OLD = "68HlXiUn1Ncg15LUJ9KreAQl6YpPtCV42ivaTBprlGs="
    KEY_UNREGISTERED = "h_QW3-8sO3K4qg4J47e_1jO1o8X4B4s5W6y7Z8a9B0c="

    def setUp(self):
        super().setUp()
        self.adapter = AcervoMFAAdapter()
        self.user = User.objects.create_user(
            username="mfa_user",
            cohort_number=31,
            password="test-password-1234",
        )

    def test_configured_adapter_is_acervo_mfa_adapter(self):
        adapter = get_adapter()
        self.assertIsInstance(adapter, AcervoMFAAdapter)
        self.assertEqual(settings.MFA_ADAPTER, "accounts.adapters.AcervoMFAAdapter")

    def test_encrypt_differs_from_plaintext_and_decrypts_back(self):
        secret = "JBSWY3DPEHPK3PXP"
        encrypted = self.adapter.encrypt(secret)

        self.assertNotEqual(encrypted, secret)
        self.assertNotIn(secret, encrypted)

        decrypted = self.adapter.decrypt(encrypted)
        self.assertEqual(decrypted, secret)

    def test_encryption_uses_primary_key(self):
        plaintext = "sensitive-secret-token"
        encrypted = self.adapter.encrypt(plaintext)

        # 先頭（プライマリ）鍵で直接復号できることを確認
        primary_fernet = Fernet(self.KEY_PRIMARY.encode("ascii"))
        decrypted_by_primary = primary_fernet.decrypt(encrypted.encode("ascii")).decode("utf-8")
        self.assertEqual(decrypted_by_primary, plaintext)

    def test_decrypt_supports_older_key_in_rotation(self):
        # 旧鍵で暗号化されたデータを作成
        old_fernet = Fernet(self.KEY_OLD.encode("ascii"))
        plaintext = "old-encrypted-secret"
        old_encrypted = old_fernet.encrypt(plaintext.encode("utf-8")).decode("ascii")

        # AcervoMFAAdapterで復号可能（ACERVO_MFA_FERNET_KEYSに含まれるため）
        decrypted = self.adapter.decrypt(old_encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_decrypt_fails_with_unregistered_key(self):
        unregistered_fernet = Fernet(self.KEY_UNREGISTERED.encode("ascii"))
        unregistered_encrypted = unregistered_fernet.encrypt(b"unauthorized-data").decode("ascii")

        with self.assertRaises(SuspiciousOperation) as ctx:
            self.adapter.decrypt(unregistered_encrypted)

        self.assertIn("MFA秘密情報の復号に失敗しました", str(ctx.exception))
        self.assertNotIn(self.KEY_UNREGISTERED, str(ctx.exception))
        self.assertNotIn("unauthorized-data", str(ctx.exception))

    def test_decrypt_fails_safely_on_invalid_ciphertext(self):
        invalid_ciphertexts = [
            "not-valid-fernet-token",
            "gAAAAABinvalid...",
            "plain-text-secret",
        ]
        for token in invalid_ciphertexts:
            with self.subTest(token=token):
                with self.assertRaises(SuspiciousOperation) as ctx:
                    self.adapter.decrypt(token)
                self.assertNotIn(token, str(ctx.exception))

    def test_totp_secret_is_encrypted_in_database(self):
        plain_secret = "JBSWY3DPEHPK3PXP"

        # allauth標準のTOTP.activateを実行
        totp = TOTP.activate(self.user, plain_secret)
        self.assertIsInstance(totp, TOTP)

        # DB上のAuthenticatorレコードを直接取得
        authenticator = Authenticator.objects.get(
            user=self.user,
            type=Authenticator.Type.TOTP,
        )
        stored_secret = authenticator.data.get("secret")

        # DB上では平文ではなく暗号文であること
        self.assertNotEqual(stored_secret, plain_secret)
        self.assertNotIn(plain_secret, stored_secret)

        # アダプター経由で復号すると元の平文と一致すること
        self.assertEqual(self.adapter.decrypt(stored_secret), plain_secret)

        # TOTPの検証処理（内部で復号が行われる）が正しく動作すること
        from allauth.mfa.totp.internal.auth import yield_hotp_counters_from_time

        current_counter = next(yield_hotp_counters_from_time())
        valid_code = format_hotp_value(hotp_value(plain_secret, current_counter))
        self.assertTrue(totp.validate_code(valid_code))

    def test_recovery_codes_seed_is_encrypted_in_database(self):
        # allauth標準のRecoveryCodes.activateを実行
        rc = RecoveryCodes.activate(self.user)
        self.assertIsInstance(rc, RecoveryCodes)

        # DB上のAuthenticatorレコードを直接取得
        authenticator = Authenticator.objects.get(
            user=self.user,
            type=Authenticator.Type.RECOVERY_CODES,
        )
        stored_seed = authenticator.data.get("seed")

        # DB上では暗号文であること
        self.assertIsNotNone(stored_seed)
        decrypted_seed = self.adapter.decrypt(stored_seed)
        self.assertNotEqual(stored_seed, decrypted_seed)

        # リカバリーコードの生成・検証が正常に行えること
        codes = rc.get_unused_codes()
        self.assertEqual(len(codes), 10)

        # 1つのコードを検証（消費）できること
        first_code = codes[0]
        self.assertTrue(rc.validate_code(first_code))
        self.assertFalse(rc.validate_code(first_code))  # 二重使用不可
