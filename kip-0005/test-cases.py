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
        message_hash = blake2b(digest_size=32, key=bytes("PersonalMessageSigningHash", "ascii"))
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
        print("Received:\t", sig.hex().upper())
        print("Expecting:\t", self.expected_signature.hex().upper())
        is_passed = (self.expected_signature == sig) == self.expected_verification_result
        assert(is_passed)

        is_passed = is_passed and (self.verify_message_signature(self.expected_signature) == self.expected_verification_result)
        print("Test Result:\t", is_passed)
        assert(is_passed)

if __name__ == "__main__":
    # Test Case 0
    print('Running Test Case 0')
    print('-------------------')
    TestCase(
        'Hello Kaspa!',
        bytes.fromhex('0000000000000000000000000000000000000000000000000000000000000003'),
        bytes.fromhex('F9308A019258C31049344F85F89D5229B531C845836F99B08601F113BCE036F9'),
        bytes_from_int(0),
        bytes.fromhex('40B9BB2BE0AE02607279EDA64015A8D86E3763279170340B8243F7CE5344D77AFF1191598BAF2FD26149CAC3B4B12C2C433261C00834DB6098CB172AA48EF522'),
        True
    ).run_test_case()
    print('')

    # Test Case 1
    print('Running Test Case 1')
    print('-------------------')
    TestCase(
        'Hello Kaspa!',
        bytes.fromhex('B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF'),
        bytes.fromhex('DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659'),
        bytes_from_int(1),
        bytes.fromhex('EB9E8A3C547EB91B6A7592644F328F0648BDD21ABA3CD44787D429D4D790AA8B962745691F3B472ED8D65F3B770ECB4F777BD17B1D309100919B53E0E206B4C6'),
        True
    ).run_test_case()
    print('')

    # Test Case 2
    print('Running Test Case 2')
    print('-------------------')
    TestCase(
        'こんにちは世界',
        bytes.fromhex('B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF'),
        bytes.fromhex('DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659'),
        bytes_from_int(1),
        bytes.fromhex('810653D5F80206DB519672362ADD6C98DAD378844E5BA4D89A22C9F0C7092E8CECBA734FFF7922B656B4BE3F4B1F098899C95CB5C1023DCE3519208AFAFB59BC'),
        True
    ).run_test_case()
    print('')

    # Test Case 3
    print('Running Test Case 3')
    print('-------------------')
    super_long_text = '''Lorem ipsum dolor sit amet. Aut omnis amet id voluptatem eligendi sit accusantium dolorem 33 corrupti necessitatibus hic consequatur quod et maiores alias non molestias suscipit? Est voluptatem magni qui odit eius est eveniet cupiditate id eius quae aut molestiae nihil eum excepturi voluptatem qui nisi architecto?

Et aliquid ipsa ut quas enim et dolorem deleniti ut eius dicta non praesentium neque est velit numquam. Ut consectetur amet ut error veniam et officia laudantium ea velit nesciunt est explicabo laudantium sit totam aperiam.

Ut omnis magnam et accusamus earum rem impedit provident eum commodi repellat qui dolores quis et voluptate labore et adipisci deleniti. Est nostrum explicabo aut quibusdam labore et molestiae voluptate. Qui omnis nostrum At libero deleniti et quod quia.'''
    TestCase(
        super_long_text,
        bytes.fromhex('B7E151628AED2A6ABF7158809CF4F3C762E7160F38B4DA56A784D9045190CFEF'),
        bytes.fromhex('DFF1D77F2A671C5F36183726DB2341BE58FEAE1DA2DECED843240F7B502BA659'),
        bytes_from_int(1),
        bytes.fromhex('40CBBD3938867B10076BB14835557C062F5BF6A4682995FC8B0A1CD2ED986EEDAAA00CFE04F6C9E5A9546B860732E5B903CC82780228647D5375BEC3D2A4983A'),
        True
    ).run_test_case()
    print('')
