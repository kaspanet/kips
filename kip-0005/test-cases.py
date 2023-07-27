from hashlib import blake2b
from reference import *

class TestCase:
    def __init__(self,
                 raw_message: str,
                 secret_key: bytes,
                 public_key: bytes,
                 aux_rand: bytes,
                 signature: bytes,
                 verification_result: bool
        ):
        self.raw_message: bytes = bytes(raw_message, 'utf-8')
        self.secret_key: bytes = secret_key
        self.public_key: bytes = public_key
        self.aux_rand: bytes = aux_rand
        self.expected_signature: bytes = signature
        self.expected_verification_result: bool = verification_result

    def hash_message(self) -> bytes:
        message_hash = blake2b(digest_size=64, key=bytes("PersonalMessageSigningHash", "ascii"))
        message_hash.update(self.raw_message)
        
        return message_hash.digest()

    def sign_message(self) -> bytes:
        message_digest = self.hash_message()

        return schnorr_sign(message_digest, self.secret_key, self.aux_rand)

    def verify_message_signature(self, message_signature: bytes) -> bool:   
        message_digest = self.hash_message()

        return schnorr_verify(message_digest, self.public_key, message_signature)

    def run_test_case(self):
        sig = self.sign_message()
        print(sig.hex().upper())
        is_passed = (self.expected_signature == sig) == self.expected_verification_result
        assert(is_passed)

        is_passed = is_passed and (self.verify_message_signature(self.expected_signature) == self.expected_verification_result)
        print(is_passed)
        assert(is_passed)
        

if __name__ == "__main__":
    # Test Case 0
    TestCase(
        'Hello Kaspa!',
        bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000003'),
        bytes.fromhex('F9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9'),
        bytes_from_int(0),
        bytes.fromhex('2BF8CBDBA646AFF947EEAF2E63C6AEF7C0A091E9412DD5A4F1ABE2C99C4BE00DEE6B4D162B0B488FF32EA4062E2E816BE60CBA5B4A3A4F26076A558EA887BF38'),
        True
    ).run_test_case()

    # Test Case 1
    TestCase(
        'Hello Kaspa!',
        bytes.fromhex('B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF'),
        bytes.fromhex('DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659'),
        bytes_from_int(1),
        bytes.fromhex('230307A47C69695235219AB059EE3A0CE7E1CA4243D7D9A4535734DE11F16B8789916C96A75DA37193C74A1C7130830F1337CBC6764CF36EB780321E25DF8511'),
        True
    ).run_test_case()

    # Test Case 2
    TestCase(
        'こんにちは世界',
        bytes.fromhex('B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF'),
        bytes.fromhex('DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659'),
        bytes_from_int(1),
        bytes.fromhex('276795139B6F6365804BB38DF717F6C826BC5F847190A4B7FA3797DFF0E78AE3CC4D4B4B7308929071627CC29BC4585F85E586901B020BFDA243354B9C3AFDD7'),
        True
    ).run_test_case()

    # Test Case 3
    super_long_text = '''Lorem ipsum dolor sit amet. Aut omnis amet id voluptatem eligendi sit accusantium dolorem 33 corrupti necessitatibus hic consequatur quod et maiores alias non molestias suscipit? Est voluptatem magni qui odit eius est eveniet cupiditate id eius quae aut molestiae nihil eum excepturi voluptatem qui nisi architecto?

Et aliquid ipsa ut quas enim et dolorem deleniti ut eius dicta non praesentium neque est velit numquam. Ut consectetur amet ut error veniam et officia laudantium ea velit nesciunt est explicabo laudantium sit totam aperiam.

Ut omnis magnam et accusamus earum rem impedit provident eum commodi repellat qui dolores quis et voluptate labore et adipisci deleniti. Est nostrum explicabo aut quibusdam labore et molestiae voluptate. Qui omnis nostrum At libero deleniti et quod quia.'''
    TestCase(
        super_long_text,
        bytes.fromhex('B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF'),
        bytes.fromhex('DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659'),
        bytes_from_int(1),
        bytes.fromhex('2057BDBBEC319F0E178FEB16CD1ED7DC77FABEF1AACA292254234C4D5EB1F3D74D702EEE975712E8C532B2690CB0530FB8C39F1C18260E8093A3E00A9EB388BB'),
        True
    ).run_test_case()

    # Test Case 4
    TestCase(
        'Hello Kaspa!',
        bytes.fromhex('B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF'),
        bytes.fromhex('DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659'),
        bytes_from_int(1),
        bytes.fromhex('2057BDBBEC319F0E178FEB16CD1ED7DC77FABEF1AACA292254234C4D5EB1F3D74D702EEE975712E8C532B2690CB0530FB8C39F1C18260E8093A3E00A9EB388BB'),
        False
    ).run_test_case()