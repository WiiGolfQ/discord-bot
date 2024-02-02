import discord

class AreYouSureView(discord.ui.View):
    
    def __init__(self, user_id):
        super().__init__(timeout=30)
        self.user_id = user_id
    
    @discord.ui.button(label='Yes', style=discord.ButtonStyle.success)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        if self.check(interaction):
            await interaction.response.defer()
            self.value = True
            self.stop()
        else:
            await interaction.response.send_message("This confirmation is not yours", ephemeral=True)
        
    @discord.ui.button(label='No', style=discord.ButtonStyle.danger)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        if self.check(interaction):
            await interaction.response.defer()
            self.value = False
            self.stop()
        else:
            await interaction.response.send_message("This confirmation is not yours", ephemeral=True)
        
    def check(self, interaction: discord.Interaction):
        return interaction.user.id == self.user_id

async def are_you_sure(ctx, prompt="Are you sure?"):
        
    view = AreYouSureView(ctx.author.id)
    message = await ctx.respond(prompt, view=view, ephemeral=True)
    await view.wait()  # Wait for the View to stop interacting.
    
    return view.value, message  # True if the confirm button was pressed.