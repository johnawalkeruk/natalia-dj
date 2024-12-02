import os
import io
import vlc
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
from PIL import Image, ImageTk
from langchain_ollama import OllamaLLM
import requests
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC

# Eleven Labs API and voice settings
ELEVEN_LABS_API_KEY = "sk_69a7d19910af18d451c7d5768e20b3ffabb043d150460e09"
ELEVEN_LABS_URL = "https://api.elevenlabs.io/v1/text-to-speech"
VOICE_ID = "nLstxwotErSY9X0Ft1Zr"

# Initialize the OllamaLLM model
model = OllamaLLM(model="llama3", base_url="http://localhost:11434")

# Updated template for intros
template = """
You are a charismatic radio DJ for "Interloper Radio." Your goal is to introduce the next track with energy and personality. Keep it concise, engaging, and always include the track title, artist, and the name of the station ("Interloper Radio"). 
Your name is "Natalia" keep it breif 
Write an engaging introduction for the song, keep it short and punchy '{title}' by '{artist}'.
"""

# Music directory
MUSIC_DIR = r"d:\music"
OUTPUT_DIR = r"d:\music\outputplaylist"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_metadata(file_path):
    """Extract metadata, including album art, from an MP3 file."""
    try:
        audio = MP3(file_path, ID3=EasyID3)
        title = audio.get("title", ["Unknown Title"])[0]
        artist = audio.get("artist", ["Unknown Artist"])[0]

        album_art = None
        try:
            tags = ID3(file_path)
            for tag in tags.values():
                if isinstance(tag, APIC):  # Album art
                    album_art = tag.data
                    break
        except:
            pass

        return title, artist, album_art
    except Exception as e:
        print(f"Error reading metadata for {file_path}: {e}")
        base_name = os.path.basename(file_path)
        parts = base_name.rsplit("-", 1)
        if len(parts) == 2:
            artist, title = parts
            return title.strip().replace(".mp3", ""), artist.strip(), None
        return "Unknown Title", "Unknown Artist", None


def generate_intro(title, artist):
    """Generate a snappy intro using Ollama."""
    prompt = template.format(title=title, artist=artist)
    response = model.invoke(input=prompt)
    return response.strip() if response else f"Here’s '{title}' by {artist} – only on Interloper Radio!"


def text_to_speech(text, output_path):
    """Generate speech from text using ElevenLabs."""
    headers = {
        "xi-api-key": ELEVEN_LABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": text,
        "voice_settings": {
            "stability": 0.75,
            "similarity_boost": 0.75,
        },
    }
    response = requests.post(f"{ELEVEN_LABS_URL}/{VOICE_ID}", json=payload, headers=headers)
    if response.status_code == 200:
        with open(output_path, "wb") as audio_file:
            audio_file.write(response.content)
        return output_path
    else:
        print(f"Error: {response.status_code} - {response.json()}")
        return None


class MusicPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Music Player")
        self.root.geometry("800x500")
        self.root.config(bg="black")

        self.playlist = []
        self.current_index = 0
        self.player = vlc.MediaPlayer()
        self.album_art = None
        self.is_playing_intro = False

        # Playlist Display
        playlist_frame = tk.Frame(self.root, bg="black")
        playlist_frame.pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.playlist_box = tk.Listbox(playlist_frame, bg="black", fg="white", selectbackground="green", width=30)
        self.playlist_box.pack(pady=10, fill=tk.BOTH, expand=True)
        self.playlist_box.bind("<<ListboxSelect>>", self.on_playlist_click)

        # Album Art
        self.album_art_label = tk.Label(self.root, bg="black")
        self.album_art_label.pack(pady=10)

        # Playback Controls
        controls_frame = tk.Frame(self.root, bg="black")
        controls_frame.pack()

        self.prev_button = tk.Button(controls_frame, text="<<", command=self.previous_track, bg="black", fg="white")
        self.play_button = tk.Button(controls_frame, text="Play", command=self.play_music, bg="black", fg="white")
        self.pause_button = tk.Button(controls_frame, text="Pause", command=self.pause_music, bg="black", fg="white")
        self.stop_button = tk.Button(controls_frame, text="Stop", command=self.stop_music, bg="black", fg="white")
        self.next_button = tk.Button(controls_frame, text=">>", command=self.next_track, bg="black", fg="white")

        self.prev_button.grid(row=0, column=0, padx=10)
        self.play_button.grid(row=0, column=1, padx=10)
        self.pause_button.grid(row=0, column=2, padx=10)
        self.stop_button.grid(row=0, column=3, padx=10)
        self.next_button.grid(row=0, column=4, padx=10)

        # Volume Control
        self.volume_slider = ttk.Scale(self.root, from_=0, to=100, orient="horizontal", command=self.set_volume)
        self.volume_slider.set(50)  # Default volume
        self.volume_slider.pack(pady=10)

        # Progress Bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(
            self.root, from_=0, to=100, orient="horizontal", variable=self.progress_var, state="disabled"
        )
        self.progress_bar.pack(pady=10)

        # Initialize Playlist
        self.load_playlist()

    def load_playlist(self):
        """Load songs and intros into the playlist."""
        for file_name in os.listdir(MUSIC_DIR):
            if file_name.endswith(".mp3"):
                file_path = os.path.join(MUSIC_DIR, file_name)
                title, artist, album_art = get_metadata(file_path)

                # Generate and save intro
                intro_text = generate_intro(title, artist)
                intro_audio_path = os.path.join(OUTPUT_DIR, f"{title}_intro.mp3")
                text_to_speech(intro_text, intro_audio_path)

                # Add intro and song to playlist
                self.playlist.append((intro_audio_path, None))  # No album art for intros
                self.playlist.append((file_path, album_art))

                # Update playlist display
                self.playlist_box.insert(tk.END, f"{title} - {artist}")

    def on_playlist_click(self, event):
        """Handle clicking a track in the playlist."""
        selection = self.playlist_box.curselection()
        if selection:
            self.current_index = selection[0] * 2  # Adjust for intro and song pair
            self.play_music()

    def play_music(self):
        """Play the current track."""
        if not self.playlist:
            messagebox.showerror("Error", "Playlist is empty!")
            return

        current_track, album_art = self.playlist[self.current_index]

        # Check if it's an intro
        self.is_playing_intro = self.current_index % 2 == 0

        self.player.set_media(vlc.Media(current_track))
        self.player.play()

        # Display album art
        self.display_album_art(album_art)

        # Check for track end and play next automatically
        self.root.after(1000, self.update_progress)

    def update_progress(self):
        """Update the progress bar and check for track end."""
        if self.player.get_length() > 0:
            progress = (self.player.get_time() / self.player.get_length()) * 100
            self.progress_var.set(progress)

        if self.player.get_state() == vlc.State.Ended:
            if self.is_playing_intro:
                self.is_playing_intro = False
                self.current_index += 1  # Move to the song
                self.play_music()
            else:
                self.next_track()
        else:
            self.root.after(1000, self.update_progress)

    def display_album_art(self, album_art):
        """Display album art if available."""
        if album_art:
            image = Image.open(io.BytesIO(album_art))
            image = image.resize((200, 200))
            album_image = ImageTk.PhotoImage(image)
            self.album_art_label.config(image=album_image)
            self.album_art_label.image = album_image
        else:
            self.album_art_label.config(image=None)

    def pause_music(self):
        """Pause the current track."""
        self.player.pause()

    def stop_music(self):
        """Stop playback."""
        self.player.stop()
        self.progress_var.set(0)

    def next_track(self):
        """Play the next track in the playlist."""
        self.stop_music()
        self.current_index = (self.current_index + 1) % len(self.playlist)
        self.play_music()

    def previous_track(self):
        """Play the previous track in the playlist."""
        self.stop_music()
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.play_music()

    def set_volume(self, volume):
        """Set the player volume."""
        self.player.audio_set_volume(int(float(volume)))


if __name__ == "__main__":
    root = tk.Tk()
    app = MusicPlayer(root)
    root.mainloop()
