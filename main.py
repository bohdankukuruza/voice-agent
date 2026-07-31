import asyncio
import base64
import http
import json
import urllib.parse
import websockets
import os
from dotenv import load_dotenv
from pharmacy_functions import FUNCTION_MAP, init_db

load_dotenv()

CALL_TIME_LIMIT_SECONDS = int(os.getenv("CALL_TIME_LIMIT_SECONDS", "60"))
STREAM_AUTH_TOKEN = os.getenv("STREAM_AUTH_TOKEN")


def sts_connect():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    if not api_key:
        raise Exception("DEEPGRAM_API_KEY not found")

    sts_ws = websockets.connect(
        "wss://agent.deepgram.com/v1/agent/converse",
        subprotocols=["token", api_key]
    )
    return sts_ws


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


async def handle_barge_in(decoded, twilio_ws, streamsid):
    if decoded["type"] == "UserStartedSpeaking":
        clear_message = {
            "event": "clear",
            "streamSid": streamsid
        }
        await twilio_ws.send(json.dumps(clear_message))


def execute_function_call(func_name, arguments):
    if func_name in FUNCTION_MAP:
        result = FUNCTION_MAP[func_name](**arguments)
        print(f"Function call result: {result}")
        return result
    else:
        result = {"error": f"Unknown function: {func_name}"}
        print(result)
        return result


def create_function_call_response(func_id, func_name, result):
    return {
        "type": "FunctionCallResponse",
        "id": func_id,
        "name": func_name,
        "content": json.dumps(result)
    }


async def handle_function_call_request(decoded, sts_ws):
    try:
        for function_call in decoded["functions"]:
            func_name = function_call["name"]
            func_id = function_call["id"]
            arguments = json.loads(function_call["arguments"])

            print(f"Function call: {func_name} (ID: {func_id}), arguments: {arguments}")

            result = execute_function_call(func_name, arguments)

            function_result = create_function_call_response(func_id, func_name, result)
            await sts_ws.send(json.dumps(function_result))
            print(f"Sent function result: {function_result}")

    except Exception as e:
        print(f"Error calling function: {e}")
        error_result = create_function_call_response(
            func_id if "func_id" in locals() else "unknown",
            func_name if "func_name" in locals() else "unknown",
            {"error": f"Function call failed with: {str(e)}"}
        )
        await sts_ws.send(json.dumps(error_result))


async def handle_text_message(decoded, twilio_ws, sts_ws, streamsid):
    await handle_barge_in(decoded, twilio_ws, streamsid)

    if decoded["type"] == "FunctionCallRequest":
        await handle_function_call_request(decoded, sts_ws)


async def sts_sender(sts_ws, audio_queue):
    print("sts_sender started")
    while True:
        chunk = await audio_queue.get()
        await sts_ws.send(chunk)


async def sts_receiver(sts_ws, twilio_ws, streamsid_queue):
    print("sts_receiver started")
    streamsid = await streamsid_queue.get()

    async for message in sts_ws:
        if type(message) is str:
            print(message)
            decoded = json.loads(message)
            await handle_text_message(decoded, twilio_ws, sts_ws, streamsid)
            continue

        raw_mulaw = message

        media_message = {
            "event": "media",
            "streamSid": streamsid,
            "media": {"payload": base64.b64encode(raw_mulaw).decode("ascii")}
        }

        await twilio_ws.send(json.dumps(media_message))


async def twilio_receiver(twilio_ws, audio_queue, streamsid_queue):
    BUFFER_SIZE = 160
    inbuffer = bytearray(b"")

    async for message in twilio_ws:
        try:
            data = json.loads(message)
            event = data["event"]

            if event == "start":
                print("get our streamsid")
                start = data["start"]
                streamsid = start["streamSid"]
                streamsid_queue.put_nowait(streamsid)
            elif event == "connected":
                continue
            elif event == "media":
                media = data["media"]
                chunk = base64.b64decode(media["payload"])
                if media["track"] == "inbound":
                    inbuffer.extend(chunk)
            elif event == "stop":
                break

            while len(inbuffer) >= BUFFER_SIZE:
                chunk = inbuffer[:BUFFER_SIZE]
                audio_queue.put_nowait(chunk)
                inbuffer = inbuffer[BUFFER_SIZE:]
        except Exception as e:
            print(f"twilio_receiver error: {e}")
            break


async def enforce_call_time_limit(sts_ws):
    await asyncio.sleep(CALL_TIME_LIMIT_SECONDS)
    print(f"Call time limit ({CALL_TIME_LIMIT_SECONDS}s) reached, ending call.")
    try:
        await sts_ws.send(json.dumps({
            "type": "InjectAgentMessage",
            "message": "We've reached our maximum call length. Thank you for calling, goodbye!"
        }))
        await asyncio.sleep(5)
    except Exception as e:
        print(f"Error sending closing message: {e}")


async def twilio_handler(twilio_ws):
    audio_queue = asyncio.Queue()
    streamsid_queue = asyncio.Queue()

    async with sts_connect() as sts_ws:
        config_message = load_config()
        await sts_ws.send(json.dumps(config_message))

        tasks = [
            asyncio.ensure_future(sts_sender(sts_ws, audio_queue)),
            asyncio.ensure_future(sts_receiver(sts_ws, twilio_ws, streamsid_queue)),
            asyncio.ensure_future(twilio_receiver(twilio_ws, audio_queue, streamsid_queue)),
            asyncio.ensure_future(enforce_call_time_limit(sts_ws)),
        ]

        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

        for task in done:
            exc = task.exception()
            if exc is not None and not isinstance(exc, asyncio.CancelledError):
                print(f"Call task ended with error: {exc!r}")

    await twilio_ws.close()


def serve_twiml(connection):
    domain = os.getenv("DOMAIN")
    # The token goes in the URL path, not the query string: Twilio drops query
    # parameters from <Stream url> but preserves the path.
    stream_url = f"wss://{domain}/"
    if STREAM_AUTH_TOKEN:
        stream_url = f"wss://{domain}/{STREAM_AUTH_TOKEN}"
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        "<Response>\n"
        "  <Connect>\n"
        f'    <Stream url="{stream_url}" />\n'
        "  </Connect>\n"
        "</Response>\n"
    )
    response = connection.respond(http.HTTPStatus.OK, twiml)
    del response.headers["Content-Type"]
    response.headers["Content-Type"] = "text/xml"
    return response


def validate_stream_request(connection, request):
    parsed = urllib.parse.urlparse(request.path)

    # Twilio's voice webhook fetches TwiML from here over plain HTTPS, so the
    # Stream URL (with its token) never has to be copy-pasted by hand.
    if parsed.path == "/twiml":
        return serve_twiml(connection)

    if not STREAM_AUTH_TOKEN:
        return None

    # Token in the path (what our TwiML emits), with query-string fallback for
    # manual testing. Stray whitespace is stripped defensively.
    path_token = urllib.parse.unquote(parsed.path).strip("/").strip()
    query_token = urllib.parse.parse_qs(parsed.query).get("token", [""])[0].strip()
    if STREAM_AUTH_TOKEN not in (path_token, query_token):
        return connection.respond(http.HTTPStatus.FORBIDDEN, "Forbidden\n")
    return None


async def main():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    init_db()
    await websockets.serve(
        twilio_handler, host, port, process_request=validate_stream_request
    )
    print(f"Started server on {host}:{port}.")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())