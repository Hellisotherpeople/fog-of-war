import numpy as np

from glm53_samplers.dry import BreakerResolver, TokenHistory


def test_default_breakers_include_embedded_surface_text_and_ignore_padding():
    class Tokenizer:
        pieces = ["hello", "\n", "hello:\n", 'a"', "***", "normal"]
        def __len__(self): return len(self.pieces)
        def batch_decode(self, ids, **kwargs): return [self.pieces[i[0]] for i in ids]
        def encode(self, text, **kwargs): raise AssertionError("Single-character breakers have no tails")
    resolver = BreakerResolver(Tokenizer(), 8)
    result = resolver.resolve(("\n", ":", '"', "*"))
    assert result == {1: ((),), 2: ((),), 3: ((),), 4: ((),)}
    assert resolver.resolve(("\n", ":", '"', "*")) is result


def test_multitoken_breaker_starting_inside_a_token():
    class Tokenizer:
        pieces = ["END", "fooE", "ND", "nope"]
        def __len__(self): return 4
        def batch_decode(self, ids, **kwargs): return [self.pieces[i[0]] for i in ids]
        def encode(self, text, **kwargs):
            assert text == "ND"
            return [2]
    resolver = BreakerResolver(Tokenizer(), 4)
    assert resolver.resolve(("END",)) == {0: ((),), 1: ((2,),)}


def test_history_grows_to_native_context_without_truncation():
    output = []
    history = TokenHistory([1] * 1048000, output, 1048576)
    history.refresh()
    output.extend([2] * 576)
    data = history.refresh()
    assert len(data) == 1048576
    assert data[0] == 1 and data[-1] == 2
